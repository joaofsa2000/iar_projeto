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
                # Verifica colisões com outros carros
                if not await self.is_colliding():
                    await self.move()
                    self.env.update_car_position(self.id, self.car.sprites()[0].get_car_position())
                else:
                    self.car.sprites()[0].stop_car()

                self.car.sprites()[0].update()

            async def move(self):
                is_tl_collided, tl_id = self.env.collision_traffic_light(self.car.sprites()[0])

                # Semáforo vermelho -> carro parado
                if is_tl_collided and self.env.get_traffic_light_status(tl_id) == LightStatus.RED:
                    self.car.sprites()[0].stop_car()
                    self.car.stopped_at_tl_id = tl_id
                    self.car.stopped_at_tl_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    await self.set_cars_at_traffic_light(tl_id)

                    # Track waiting time for green light request
                    if self.agent.waiting_start_time is None:
                        self.agent.waiting_start_time = datetime.now()
                    
                    # Check if we should request green light
                    await self.check_and_request_green(tl_id)

                    # FIPA SUBSCRIBE PROTOCOL - Subscreve ao semáforo se ainda não subscreveu
                    # Cancela subscrição anterior se mudou de semáforo
                    if self.agent.current_traffic_light and self.agent.current_traffic_light != tl_id:
                        await self.cancel_subscription(self.agent.current_traffic_light)

                    if self.agent.current_traffic_light != tl_id:
                        await self.subscribe_to_traffic_light(tl_id)
                        self.agent.current_traffic_light = tl_id
                else:
                    # Cancelar subscrição anterior se mudou de semáforo
                    if self.agent.current_traffic_light and not is_tl_collided:
                        await self.cancel_subscription(self.agent.current_traffic_light)
                        self.agent.current_traffic_light = None

                    # Reset waiting time tracking when moving
                    self.agent.waiting_start_time = None
                    self.agent.green_request_sent = False

                    if self.env.collision_sprite(self.car.sprites()[0]):
                        self.car.sprites()[0].fires_car()
                        self.car.sprites()[0].activate_turning()
                        self.car.sprites()[0].flag_car_is_turning(True)
                    else:
                        self.car.sprites()[0].flag_car_is_turning(False)
                        self.car.sprites()[0].fires_car()

                    if hasattr(self.car, 'stopped_at_tl_start_time') and self.car.stopped_at_tl_start_time:
                        await self.set_cars_stopped_times()

                    self.car.stopped_at_tl_id = False

            async def check_and_request_green(self, tl_id):
                """Check waiting time and request green light if threshold exceeded."""
                if self.agent.green_request_sent:
                    return
                
                if self.agent.waiting_start_time:
                    waiting_duration = (datetime.now() - self.agent.waiting_start_time).total_seconds()
                    
                    if waiting_duration >= GREEN_REQUEST_THRESHOLD:
                        await self.request_green_light(tl_id)
                        self.agent.green_request_sent = True

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
                print(f"[CAR {self.agent.jid}] REQUEST GREEN enviado para {tl_jid} (esperando há mais de {GREEN_REQUEST_THRESHOLD}s)")

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
                print(f"[CAR {self.agent.jid}] SUBSCRIBE enviado para {tl_jid}")

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
                    print(f"[CAR {self.agent.jid}] CANCEL enviado para {tl_jid}")

            async def set_cars_stopped_times(self):
                difference = self.calc_time_difference(self.car.stopped_at_tl_start_time,
                                                       datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                if difference:
                    self.env.cars_stopped_times.append(
                        (self.car.stopped_at_tl_id, self.car.sprites()[0].id, difference))
                self.car.stopped_at_tl_start_time = False

            def calc_time_difference(self, start_time, end_time):
                time_format = "%Y-%m-%d %H:%M:%S"
                start = datetime.strptime(start_time, time_format)
                end = datetime.strptime(end_time, time_format)
                difference = end - start

                return str(difference) if difference > timedelta(0) else False

            async def set_cars_at_traffic_light(self, tl_id):
                if tl_id not in self.env.cars_stopped_at_tl:
                    self.env.cars_stopped_at_tl[tl_id] = []

                if self.id not in self.env.cars_stopped_at_tl[tl_id]:
                    self.env.cars_stopped_at_tl[tl_id].append(self.id)

            async def is_colliding(self):
                angle = self.car.sprites()[0].angle
                coordinates = self.env.car_positions[self.id]

                limit = await self.get_value_by_angle(angle)

                if (abs(angle / 90) % 2) == 0:
                    value_to_check = coordinates[1] + limit
                    static_value_to_check = coordinates[0]
                else:
                    value_to_check = coordinates[0] + limit
                    static_value_to_check = coordinates[1]

                for env_car in self.env.car_positions.keys():
                    if env_car == self.id:
                        continue

                    if (abs(angle / 90) % 2) == 0:
                        other_value = self.env.car_positions[env_car][1]
                        other_static = self.env.car_positions[env_car][0]
                    else:
                        other_value = self.env.car_positions[env_car][0]
                        other_static = self.env.car_positions[env_car][1]

                    if (other_value - 1 <= value_to_check <= other_value + 1) and (
                            other_static - 7 <= static_value_to_check <= other_static + 7):
                        if hasattr(self.env.get_car_by_id(env_car), 'stopped_at_tl_id'):
                            tl_id = self.env.get_car_by_id(env_car).stopped_at_tl_id
                            if tl_id:
                                self.car.stopped_at_tl_id = tl_id
                                await self.set_cars_at_traffic_light(tl_id)

                        return True

                return False

            async def get_value_by_angle(self, angle):
                if angle in [0, 90, 360, -270, -360]:
                    return -38
                elif angle in [180, 270, -90, -180]:
                    return 38
                else:
                    return 0

        self.add_behaviour(MovementBehaviour(self))

        # Comportamento para receber notificações dos semáforos
        class ReceiveNotificationBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)

                if msg and msg.get_metadata("protocol") == "fipa-subscribe":
                    performative = msg.get_metadata("performative")
                    conv_id = msg.get_metadata("conversation-id")

                    if performative == "agree":
                        # Subscrição aceite
                        subscription_id = msg.get_metadata("subscription-id")
                        self.agent.subscribed_traffic_lights[str(msg.sender)] = subscription_id
                        print(f"[CAR {self.agent.jid}] Subscrição confirmada por {msg.sender}")
                        print(f"[CAR {self.agent.jid}] Status inicial: {msg.body}")

                    elif performative == "inform":
                        # Notificação de mudança de estado
                        print(f"[CAR {self.agent.jid}] Atualização recebida: {msg.body}")

                        # Aqui pode processar a mudança de estado
                        if "GREEN" in msg.body:
                            print(f"[CAR {self.agent.jid}] Semáforo ficou VERDE! Preparar para avançar")
                        elif "RED" in msg.body:
                            print(f"[CAR {self.agent.jid}] Semáforo ficou VERMELHO!")
                        elif "YELLOW" in msg.body:
                            print(f"[CAR {self.agent.jid}] Semáforo ficou AMARELO! Atenção")

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
                            print(f"[CAR {self.agent.jid}] AGREE recebido para pedido de luz verde")
                        elif performative == "inform":
                            print(f"[CAR {self.agent.jid}] INFORM recebido: {msg.body}")
                            del self.agent.pending_green_requests[conv_id]
                        elif performative == "refuse":
                            print(f"[CAR {self.agent.jid}] REFUSE recebido: {msg.body}")
                            del self.agent.pending_green_requests[conv_id]
                        elif performative == "failure":
                            print(f"[CAR {self.agent.jid}] FAILURE recebido: {msg.body}")
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
                        print(f"[CAR {self.agent.jid}] Broadcast recebido: {msg.body}")
                        # React to system alerts if needed (e.g., congestion warnings)

        template_inform = Template()
        template_inform.set_metadata("protocol", "fipa-inform")
        self.add_behaviour(ReceiveBroadcastBehaviour(), template_inform)
