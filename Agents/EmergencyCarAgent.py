from datetime import datetime, timedelta
import math
import time
import uuid
import pygame

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from Models.LightStatus import LightStatus


class EmergencyCarAgent(Agent):
    def __init__(self, jid, password, environment):
        super().__init__(jid, password)
        self.environment = environment
        self.id = jid
        self.password = password

        self.guid = uuid.uuid4()

        self.car_at_traffic_light = False
        self.car_obj = self.environment.add_emergency_car(self.id)

    async def setup(self):
        print(f"[EMERGENCY CAR {self.jid}] Agente iniciado")

        # Comportamento principal de movimento
        class MovementBehaviour(CyclicBehaviour):
            def __init__(self, agent):
                super().__init__()
                self.agent = agent
                self.id = self.agent.id
                self.car = self.agent.car_obj
                self.env = self.agent.environment
                self.request_id = None
                self.waiting_for_response = False
                self.request_sent_time = None

            async def run(self):
                # Verifica se o veículo terminou o percurso
                if self.car.sprites()[0].is_car_done():
                    print(f"[EMERGENCY CAR {self.agent.jid}] Percurso concluído")
                    await self.agent.stop()
                    return

                await self.move()
                self.car.sprites()[0].update()

            async def move(self):
                is_tl_collided, tl_id = self.env.collision_traffic_light(self.car.sprites()[0])

                if is_tl_collided and self.env.get_traffic_light_status(tl_id) == LightStatus.RED:
                    # Semáforo vermelho: veículo para
                    self.car.sprites()[0].stop_car()

                    current_wait_time = self.env.emergency_cars_awaiting_time.get(self.agent.guid, 0)
                    self.env.emergency_cars_awaiting_time[self.agent.guid] = current_wait_time + 1

                    # FIPA REQUEST PROTOCOL - Envia pedido se ainda não enviou
                    if not self.waiting_for_response:
                        await self.send_request(tl_id)
                        self.waiting_for_response = True
                        self.request_sent_time = datetime.now()

                    # Timeout: se não receber resposta em 5 segundos, muda de direção
                    if self.request_sent_time and (datetime.now() - self.request_sent_time).seconds > 5:
                        if self.env.emergency_cars_awaiting_time[self.agent.guid] > 150 and not self.car.sprites()[
                            0].is_car_changing_direction():
                            print(f"[EMERGENCY CAR {self.agent.jid}] Timeout! Mudando de direção")
                            self.car.sprites()[0].activate_changing_direction()
                            self.car.sprites()[0].change_direction(str(tl_id).split("_")[3])
                            self.waiting_for_response = False
                            self.request_sent_time = None
                            self.env.emergency_cars_awaiting_time[self.agent.guid] = 0
                else:
                    # Semáforo verde ou não há semáforo: continua
                    self.env.emergency_cars_awaiting_time[self.agent.guid] = 0
                    self.car.sprites()[0].disable_changing_direction()
                    self.car.stopped_at_tl_id = False
                    self.waiting_for_response = False
                    self.request_sent_time = None

                    if self.env.collision_sprite(self.car.sprites()[0]):
                        self.car.sprites()[0].fires_car()
                        self.car.sprites()[0].activate_turning()
                        self.car.sprites()[0].flag_car_is_turning(True)
                    else:
                        self.car.sprites()[0].flag_car_is_turning(False)
                        self.car.sprites()[0].fires_car()

            async def send_request(self, tl_id):
                """Envia REQUEST seguindo o FIPA Request Protocol"""
                tl_jid = self.env.get_traffic_light_jid_by_id(tl_id)
                self.request_id = str(uuid.uuid4())

                msg = Message(to=tl_jid)
                msg.set_metadata("performative", "request")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", self.request_id)
                msg.set_metadata("traffic_light_id", str(tl_id))
                msg.body = f"EMERGENCY_REQUEST: Vehicle {self.agent.guid} requesting green light at {tl_id}"

                await self.send(msg)
                print(f"[EMERGENCY CAR {self.agent.jid}] REQUEST enviado para {tl_jid} (conv-id: {self.request_id})")

        self.add_behaviour(MovementBehaviour(self))

        # Comportamento para receber respostas dos semáforos (AGREE/REFUSE/INFORM)
        class ReceiveResponseBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)

                if msg:
                    performative = msg.get_metadata("performative")
                    conv_id = msg.get_metadata("conversation-id")

                    if performative == "agree":
                        print(f"[EMERGENCY CAR {self.agent.jid}] AGREE recebido (conv-id: {conv_id})")
                        # O semáforo concordou em processar o pedido

                    elif performative == "refuse":
                        print(f"[EMERGENCY CAR {self.agent.jid}] REFUSE recebido (conv-id: {conv_id})")
                        print(f"[EMERGENCY CAR {self.agent.jid}] Motivo: {msg.body}")
                        # Semáforo recusou - implementar lógica alternativa

                    elif performative == "inform":
                        print(f"[EMERGENCY CAR {self.agent.jid}] INFORM recebido (conv-id: {conv_id})")
                        print(f"[EMERGENCY CAR {self.agent.jid}] Status: {msg.body}")
                        # Semáforo informou sobre a conclusão da ação

                    elif performative == "failure":
                        print(f"[EMERGENCY CAR {self.agent.jid}] FAILURE recebido (conv-id: {conv_id})")
                        print(f"[EMERGENCY CAR {self.agent.jid}] Erro: {msg.body}")

        template = Template()
        template.set_metadata("protocol", "fipa-request")
        self.add_behaviour(ReceiveResponseBehaviour(), template)