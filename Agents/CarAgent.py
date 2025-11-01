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

        template = Template()
        template.set_metadata("protocol", "fipa-subscribe")
        self.add_behaviour(ReceiveNotificationBehaviour(), template)