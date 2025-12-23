# CarAgent.py

from datetime import datetime, timedelta
import math
import time
import uuid
import pygame

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message
from spade.template import Template

from Models.LightStatus import LightStatus
from Models.Directions import Directions
from Data.MetricsManager import get_metrics_manager


# Threshold in seconds before requesting green light
GREEN_REQUEST_THRESHOLD = 30


class CarAgent(Agent):
    def __init__(self, jid, password, environment):
        super().__init__(jid, password)
        self.environment = environment
        self.id = jid

        self.car_at_traffic_light = False
        self.car_obj = self.environment.add_car(self.id)

        # Controlo de subscrições aos semáforos
        self.subscribed_traffic_lights = {}  # {tl_jid: subscription_id}
        self.current_traffic_light = None
        
        # Waiting time tracking for green light requests
        self.waiting_start_time = None
        self.green_request_sent = False
        self.pending_green_requests = {}  # {conv_id: tl_jid}

    async def setup(self):
        print(f"[CAR {self.jid}] Agente iniciado")

        class MovementBehaviour(CyclicBehaviour):
            def __init__(self, agent):
                super().__init__()
                self.agent = agent

                self.id = self.agent.id
                self.car = self.agent.car_obj
                self.env = self.agent.environment

            async def run(self):
                car_sprite = self.car.sprites()[0]
                
                # Check if car has left the map
                if car_sprite.rect.x < -100 or car_sprite.rect.x > 1400 or car_sprite.rect.y > 850 or car_sprite.rect.y < -100:
                    # Remove car from environment tracking
                    if self.id in self.env.car_positions:
                        del self.env.car_positions[self.id]
                    # Clear waiting time
                    self.env.stop_car_waiting(self.id)
                    
                    # Remove car from cars_stopped_at_tl if it was stopped
                    # Check all traffic lights and remove this car
                    for tl_id in list(self.env.cars_stopped_at_tl.keys()):
                        if self.id in self.env.cars_stopped_at_tl[tl_id]:
                            self.env.cars_stopped_at_tl[tl_id].remove(self.id)
                            # Clean up empty lists
                            if not self.env.cars_stopped_at_tl[tl_id]:
                                del self.env.cars_stopped_at_tl[tl_id]
                    
                    # Remove from cars list
                    if self.car in self.env.cars:
                        self.env.cars.remove(self.car)
                    # print(f"[CARRO {self.agent.jid}] Saiu do mapa - agente parado")
                    await self.agent.stop()
                    return
                
                # 1. Verificar colisão (AGENTE decide)
                collision_result = await self.is_colliding()
                if collision_result:
                    # Colisão detectada - parar o carro
                    car_sprite.stop_car()
                    # If car inherited stopped_at_tl_id from collision, ensure it's tracked
                    if hasattr(self.car, 'stopped_at_tl_id') and self.car.stopped_at_tl_id:
                        # Ensure car is in cars_stopped_at_tl
                        await self.set_cars_at_traffic_light(self.car.stopped_at_tl_id)
                        # Start tracking waiting time if not already tracking
                        if self.id not in self.env.car_waiting_start_times:
                            self.env.start_car_waiting(self.id)
                    # Não mover - aguardar próxima iteração
                    return
                
                # 2. Decidir movimento (AGENTE decide)
                await self.move()  # Verifica semáforos, etc.
                
                # 3. Executar física (SPRITE executa)
                if car_sprite.is_turning[0]:
                    car_sprite.handle_turning()
                elif car_sprite.is_switching_lane[0]:
                    car_sprite.switch_lane(car_sprite.is_switching_lane[1])
                elif not car_sprite.is_car_stopped:
                    car_sprite.go_forward()
                
                # 4. Atualizar posição no ambiente
                self.env.update_car_position(self.id, car_sprite.get_car_position())

            async def move(self):
                car_sprite = self.car.sprites()[0]
                is_tl_collided, tl_id = self.env.collision_traffic_light(car_sprite)

                # Get traffic light status
                tl_status = self.env.get_traffic_light_status(tl_id) if is_tl_collided else None
                
                # Handle different traffic light states
                if is_tl_collided:
                    if tl_status == LightStatus.RED:
                        # Red light - always stop
                        car_sprite.stop_car()
                        self.car.stopped_at_tl_id = tl_id
                        # Store simulation time instead of real time
                        self.car.stopped_at_tl_start_time = self.env.simulation_time.strftime("%Y-%m-%d %H:%M:%S")
                        await self.set_cars_at_traffic_light(tl_id)
                        
                        # Start tracking waiting time for visual timer
                        self.env.start_car_waiting(self.id)

                        # Track waiting time for green light request (use simulation time)
                        if self.agent.waiting_start_time is None:
                            self.agent.waiting_start_time = self.env.simulation_time
                        
                        await self.check_and_request_green(tl_id)

                        # FIPA SUBSCRIBE PROTOCOL
                        if self.agent.current_traffic_light and self.agent.current_traffic_light != tl_id:
                            await self.cancel_subscription(self.agent.current_traffic_light)

                        if self.agent.current_traffic_light != tl_id:
                            await self.subscribe_to_traffic_light(tl_id)
                            self.agent.current_traffic_light = tl_id
                    
                    elif tl_status == LightStatus.YELLOW:
                        # Yellow light - check if already crossing
                        is_crossing = self.env.is_car_crossing_traffic_light(car_sprite, tl_id)
                        
                        if is_crossing:
                            # Already crossing - continue at normal speed
                            car_sprite.resume_normal_speed()
                        else:
                            # Not yet crossing - gradual slowdown (only if not already slowing down enough)
                            # Only slow down if current speed is above target
                            target_speed = car_sprite.normal_base_speed * 0.5  # Slow down to 50% speed
                            if car_sprite.base_speed > target_speed:
                                car_sprite.slow_down(target_speed_factor=0.5)  # Slow down to 50% speed
                            # If already at target speed, maintain it (don't keep calling slow_down)
                    
                    elif tl_status == LightStatus.GREEN:
                        # Green light - resume normal speed and ensure car moves
                        car_sprite.resume_normal_speed()
                        # Clear stopped at traffic light flag when green
                        if hasattr(self.car, 'stopped_at_tl_id') and self.car.stopped_at_tl_id:
                            # Record waiting time before clearing
                            await self.set_cars_stopped_times()
                            self.car.stopped_at_tl_id = False
                        # Remove from cars_stopped_at_tl
                        if tl_id in self.env.cars_stopped_at_tl and self.id in self.env.cars_stopped_at_tl[tl_id]:
                            self.env.cars_stopped_at_tl[tl_id].remove(self.id)
                        # Stop tracking waiting time
                        self.env.stop_car_waiting(self.id)
                        # Reset waiting time tracking
                        self.agent.waiting_start_time = None
                        self.agent.green_request_sent = False
                
                # If no traffic light collision, resume normal speed (car passed the light)
                if not is_tl_collided:
                    # Resume normal speed if was slowing down
                    car_sprite.resume_normal_speed()
                    
                    # Cancelar subscrição anterior se mudou de semáforo
                    if self.agent.current_traffic_light and not is_tl_collided:
                        await self.cancel_subscription(self.agent.current_traffic_light)
                        self.agent.current_traffic_light = None

                    # Reset waiting time tracking when moving
                    self.agent.waiting_start_time = None
                    self.agent.green_request_sent = False

                    # Get waiting time BEFORE stopping it (uses simulation time)
                    # Check if car was stopped at a traffic light and record the waiting time
                    if hasattr(self.car, 'stopped_at_tl_id') and self.car.stopped_at_tl_id:
                        await self.set_cars_stopped_times()

                    # Clear stopped at traffic light flag
                    # Get old_tl_id before clearing (check both group and sprite)
                    old_tl_id = None
                    if hasattr(self.car, 'stopped_at_tl_id'):
                        old_tl_id = self.car.stopped_at_tl_id
                        self.car.stopped_at_tl_id = False
                    elif self.car.sprites():
                        car_sprite = self.car.sprites()[0]
                        if hasattr(car_sprite, 'stopped_at_tl_id'):
                            old_tl_id = car_sprite.stopped_at_tl_id
                            car_sprite.stopped_at_tl_id = False
                    
                    # Remove car from cars_stopped_at_tl when it starts moving
                    # Remove from all traffic lights to ensure complete cleanup
                    for tl_id in list(self.env.cars_stopped_at_tl.keys()):
                        if self.id in self.env.cars_stopped_at_tl[tl_id]:
                            self.env.cars_stopped_at_tl[tl_id].remove(self.id)
                            # Clean up empty lists
                            if not self.env.cars_stopped_at_tl[tl_id]:
                                del self.env.cars_stopped_at_tl[tl_id]

                    # Stop tracking waiting time for visual timer (after recording)
                    self.env.stop_car_waiting(self.id)

                    if self.env.collision_sprite(self.car.sprites()[0]):
                        self.car.sprites()[0].fires_car()
                        self.car.sprites()[0].activate_turning()
                        self.car.sprites()[0].flag_car_is_turning(True)
                    else:
                        self.car.sprites()[0].flag_car_is_turning(False)
                        self.car.sprites()[0].fires_car()

            async def check_and_request_green(self, tl_id):
                """Check waiting time and request green light if threshold exceeded."""
                if self.agent.green_request_sent:
                    return

                if self.agent.waiting_start_time:
                    # Use simulation time instead of real time
                    waiting_duration = (self.env.simulation_time - self.agent.waiting_start_time).total_seconds()

                    if waiting_duration >= GREEN_REQUEST_THRESHOLD:
                        # Check if the red light is due to an accident
                        tl_status = self.env.get_traffic_light_status(tl_id)
                        if tl_status == LightStatus.RED:
                            # Check if intersection is blocked (accident)
                            intersection_id = self._get_intersection_from_traffic_light(tl_id)
                            if intersection_id and self.env.is_intersection_blocked(intersection_id):
                                # Don't request green for accidents - just wait
                                # print(f"[CARRO {self.agent.jid}] Semáforo vermelho por acidente em {intersection_id} - aguardando")
                                return

                        await self.request_green_light(tl_id)
                        self.agent.green_request_sent = True
                        # print(f"[CAR {self.agent.jid}] REQUEST GREEN enviado para {tl_jid} (esperando há mais de {GREEN_REQUEST_THRESHOLD}s)")

            def _get_intersection_from_traffic_light(self, tl_id):
                """Extract intersection ID from traffic light ID."""
                tl_id_str = str(tl_id)

                intersection_patterns = [
                    "top_left", "top_mid", "top_right",
                    "bottom_left", "bottom_mid", "bottom_right"
                ]

                for intersection in intersection_patterns:
                    if intersection in tl_id_str:
                        return intersection

                return None

            async def request_green_light(self, tl_id):
                """Send FIPA Request to traffic light requesting green."""
                tl_jid = self.env.get_traffic_light_jid_by_id(tl_id)
                conv_id = str(uuid.uuid4())
                
                msg = Message(to=tl_jid)
                msg.set_metadata("performative", "request")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", conv_id)
                msg.set_metadata("action", "request_green")
                msg.set_metadata("traffic_light_id", str(tl_id))
                msg.body = f"GREEN_REQUEST: Car {self.id} has been waiting for {GREEN_REQUEST_THRESHOLD}+ seconds at {tl_id}"
                
                await self.send(msg)
                self.agent.pending_green_requests[conv_id] = tl_jid
                # print(f"[CAR {self.agent.jid}] REQUEST GREEN enviado para {tl_jid} (esperando há mais de {GREEN_REQUEST_THRESHOLD}s)")

            async def subscribe_to_traffic_light(self, tl_id):
                """Subscreve ao semáforo usando FIPA Subscribe Protocol"""
                tl_jid = self.env.get_traffic_light_jid_by_id(tl_id)
                conv_id = str(uuid.uuid4())

                msg = Message(to=tl_jid)
                msg.set_metadata("performative", "subscribe")
                msg.set_metadata("protocol", "fipa-subscribe")
                msg.set_metadata("conversation-id", conv_id)
                msg.body = f"CAR_SUBSCRIBE: Car {self.id} wants status updates from {tl_id}"

                await self.send(msg)
                # print(f"[CAR {self.agent.jid}] SUBSCRIBE enviado para {tl_jid}")

            async def cancel_subscription(self, tl_id):
                """Cancela subscrição ao semáforo"""
                tl_jid = self.env.get_traffic_light_jid_by_id(tl_id)

                if tl_jid in self.agent.subscribed_traffic_lights:
                    subscription_id = self.agent.subscribed_traffic_lights[tl_jid]

                    msg = Message(to=tl_jid)
                    msg.set_metadata("performative", "cancel")
                    msg.set_metadata("protocol", "fipa-subscribe")
                    msg.set_metadata("conversation-id", subscription_id)
                    msg.body = f"CAR_UNSUBSCRIBE: Car {self.id} cancelling subscription"

                    await self.send(msg)
                    del self.agent.subscribed_traffic_lights[tl_jid]
                    # print(f"[CAR {self.agent.jid}] CANCEL enviado para {tl_jid}")

            async def set_cars_stopped_times(self):
                # Use simulation time from environment instead of real time
                wait_seconds = self.env.get_car_waiting_time(self.id)
                
                # get_car_waiting_time returns None if car is not waiting, or elapsed seconds if waiting
                if wait_seconds is not None and wait_seconds > 0:
                    # Get traffic light ID - check both car group and sprite
                    tl_id = None
                    if hasattr(self.car, 'stopped_at_tl_id') and self.car.stopped_at_tl_id:
                        tl_id = self.car.stopped_at_tl_id
                    elif self.car.sprites():
                        car_sprite = self.car.sprites()[0]
                        if hasattr(car_sprite, 'stopped_at_tl_id') and car_sprite.stopped_at_tl_id:
                            tl_id = car_sprite.stopped_at_tl_id
                    
                    if tl_id:
                        # Format as HH:MM:SS for display
                        hours = int(wait_seconds // 3600)
                        minutes = int((wait_seconds % 3600) // 60)
                        seconds = int(wait_seconds % 60)
                        difference = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        
                        self.env.cars_stopped_times.append(
                            (tl_id, self.car.sprites()[0].id, difference))
                        
                        # Record to metrics manager for ML training
                        try:
                            # Get intersection from traffic light ID
                            tl_id_str = str(tl_id)
                            intersection_id = "_".join(tl_id_str.split("_")[:2]) if "_" in tl_id_str else "unknown"
                            
                            metrics = get_metrics_manager()
                            metrics.record_waiting_time(
                                sim_time=self.env.simulation_time,
                                car_id=str(self.car.sprites()[0].id),
                                traffic_light_id=tl_id_str,
                                waiting_time_seconds=wait_seconds,
                                intersection_id=intersection_id
                            )
                        except Exception as e:
                            print(f"[CAR {self.agent.jid}] Error recording waiting time: {e}")
                    
                # Clear stopped at traffic light start time flag if it exists
                if hasattr(self.car, 'stopped_at_tl_start_time'):
                    self.car.stopped_at_tl_start_time = False

            def calc_time_difference(self, start_time, end_time):
                time_format = "%Y-%m-%d %H:%M:%S"
                start = datetime.strptime(start_time, time_format)
                end = datetime.strptime(end_time, time_format)
                difference = end - start

                return str(difference) if difference > timedelta(0) else False

            async def set_cars_at_traffic_light(self, tl_id):
                """Add car to cars_stopped_at_tl for the given traffic light.
                Also removes car from any other traffic light it might be registered at."""
                if not tl_id:
                    return
                
                # Remove car from any other traffic light it might be registered at
                for other_tl_id in list(self.env.cars_stopped_at_tl.keys()):
                    if other_tl_id != tl_id and self.id in self.env.cars_stopped_at_tl[other_tl_id]:
                        self.env.cars_stopped_at_tl[other_tl_id].remove(self.id)
                        # Clean up empty lists
                        if not self.env.cars_stopped_at_tl[other_tl_id]:
                            del self.env.cars_stopped_at_tl[other_tl_id]
                
                # Add car to the new traffic light
                if tl_id not in self.env.cars_stopped_at_tl:
                    self.env.cars_stopped_at_tl[tl_id] = []

                if self.id not in self.env.cars_stopped_at_tl[tl_id]:
                    self.env.cars_stopped_at_tl[tl_id].append(self.id)

            async def is_colliding(self):
                """Check if car is about to collide with another car ahead in the SAME LANE.
                Cars in different lanes (side by side) should NOT block each other."""
                angle = self.car.sprites()[0].angle
                
                if self.id not in self.env.car_positions:
                    return False
                    
                coordinates = self.env.car_positions[self.id]

                # Detection distance ahead based on direction
                detection_distance = 40  # pixels ahead to check (balanced for safety and lane changes)
                same_lane_tolerance = 15  # STRICT - only cars in same lane

                # Normalize angle
                angle_norm = angle % 360
                if angle_norm < 0:
                    angle_norm += 360

                for env_car in self.env.car_positions.keys():
                    if env_car == self.id:
                        continue

                    other_pos = self.env.car_positions[env_car]
                    
                    # Check if other car is going in SIMILAR direction (same lane)
                    # Get other car's angle
                    other_angle = other_pos[2] if len(other_pos) > 2 else 0
                    other_angle_norm = other_angle % 360
                    if other_angle_norm < 0:
                        other_angle_norm += 360
                    
                    # Calculate angle difference
                    angle_diff = abs(angle_norm - other_angle_norm)
                    if angle_diff > 180:
                        angle_diff = 360 - angle_diff
                    
                    # Only check cars going in roughly the same direction (within 45 degrees)
                    # Cars going opposite directions are in different lanes - allow side by side
                    if angle_diff > 45:
                        continue
                    
                    dx = other_pos[0] - coordinates[0]
                    dy = other_pos[1] - coordinates[1]

                    # Check based on direction (strict same-lane detection)
                    is_blocking = False
                    
                    if 315 <= angle_norm or angle_norm < 45:  # Going up (north)
                        # Car ahead is above us (negative dy) and in same lane
                        if -detection_distance < dy < 0 and abs(dx) < same_lane_tolerance:
                            is_blocking = True
                    elif 45 <= angle_norm < 135:  # Going left (west)
                        # Car ahead is to our left (negative dx) and in same lane
                        if -detection_distance < dx < 0 and abs(dy) < same_lane_tolerance:
                            is_blocking = True
                    elif 135 <= angle_norm < 225:  # Going down (south)
                        # Car ahead is below us (positive dy) and in same lane
                        if 0 < dy < detection_distance and abs(dx) < same_lane_tolerance:
                            is_blocking = True
                    elif 225 <= angle_norm < 315:  # Going right (east)
                        # Car ahead is to our right (positive dx) and in same lane
                        if 0 < dx < detection_distance and abs(dy) < same_lane_tolerance:
                            is_blocking = True

                    if is_blocking:
                        # If other car is stopped at traffic light, inherit the stopped state
                        other_car_obj = self.env.get_car_by_id(env_car)
                        if other_car_obj:
                            # Check stopped_at_tl_id on both group and sprite
                            tl_id = None
                            if hasattr(other_car_obj, 'stopped_at_tl_id') and other_car_obj.stopped_at_tl_id:
                                tl_id = other_car_obj.stopped_at_tl_id
                            elif other_car_obj.sprites():
                                other_sprite = other_car_obj.sprites()[0]
                                if hasattr(other_sprite, 'stopped_at_tl_id') and other_sprite.stopped_at_tl_id:
                                    tl_id = other_sprite.stopped_at_tl_id
                            
                            if tl_id:
                                # Inherit stopped_at_tl_id from the blocking car
                                self.car.stopped_at_tl_id = tl_id
                                await self.set_cars_at_traffic_light(tl_id)
                                
                                # Start tracking waiting time if not already tracking
                                if self.id not in self.env.car_waiting_start_times:
                                    self.env.start_car_waiting(self.id)
                        return True

                return False

        self.add_behaviour(MovementBehaviour(self))

        # Comportamento para receber notificações dos semáforos
        class ReceiveNotificationBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)

                if msg:
                    # Template already filters by protocol, so we can process any message that arrives
                    performative = msg.get_metadata("performative")
                    conv_id = msg.get_metadata("conversation-id")

                    if performative == "agree":
                        # Subscrição aceite
                        subscription_id = msg.get_metadata("subscription-id")
                        if subscription_id:
                            self.agent.subscribed_traffic_lights[str(msg.sender)] = subscription_id
                        # print(f"[CAR {self.agent.jid}] Subscrição confirmada por {msg.sender}")
                        # print(f"[CAR {self.agent.jid}] Status inicial: {msg.body}")

                    elif performative == "inform":
                        # Notificação de mudança de estado
                        # print(f"[CAR {self.agent.jid}] Atualização recebida: {msg.body}")

                        # Aqui pode processar a mudança de estado
                        # if "GREEN" in msg.body:
                        #     print(f"[CAR {self.agent.jid}] Semáforo ficou VERDE! Preparar para avançar")
                        # elif "RED" in msg.body:
                        #     print(f"[CAR {self.agent.jid}] Semáforo ficou VERMELHO!")
                        # elif "YELLOW" in msg.body:
                        #     print(f"[CAR {self.agent.jid}] Semáforo ficou AMARELO! Atenção")
                        pass

        # Template matches any message with fipa-subscribe protocol (both AGREE and INFORM)
        template = Template()
        template.set_metadata("protocol", "fipa-subscribe")
        self.add_behaviour(ReceiveNotificationBehaviour(), template)

        # Comportamento para receber respostas de pedidos de luz verde
        class ReceiveGreenResponseBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)

                if msg and msg.get_metadata("protocol") == "fipa-request":
                    performative = msg.get_metadata("performative")
                    conv_id = msg.get_metadata("conversation-id")

                    if conv_id in self.agent.pending_green_requests:
                        if performative == "agree":
                            # print(f"[CAR {self.agent.jid}] AGREE recebido para pedido de luz verde")
                            pass
                        elif performative == "inform":
                            # print(f"[CAR {self.agent.jid}] INFORM recebido: {msg.body}")
                            del self.agent.pending_green_requests[conv_id]
                        elif performative == "refuse":
                            # print(f"[CAR {self.agent.jid}] REFUSE recebido: {msg.body}")
                            del self.agent.pending_green_requests[conv_id]
                        elif performative == "failure":
                            # print(f"[CAR {self.agent.jid}] FAILURE recebido: {msg.body}")
                            del self.agent.pending_green_requests[conv_id]

        template_request = Template()
        template_request.set_metadata("protocol", "fipa-request")
        self.add_behaviour(ReceiveGreenResponseBehaviour(), template_request)

        # Comportamento para receber alertas de broadcast
        class ReceiveBroadcastBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)
                
                if msg and msg.get_metadata("protocol") == "fipa-inform":
                    performative = msg.get_metadata("performative")
                    
                    if performative == "inform":
                        # print(f"[CAR {self.agent.jid}] Broadcast recebido: {msg.body}")
                        # React to system alerts if needed (e.g., congestion warnings)
                        pass

        template_inform = Template()
        template_inform.set_metadata("protocol", "fipa-inform")
        self.add_behaviour(ReceiveBroadcastBehaviour(), template_inform)
