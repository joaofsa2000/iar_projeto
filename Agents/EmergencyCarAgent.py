from datetime import datetime, timedelta
import math
import time
import uuid
import pygame

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.behaviour import OneShotBehaviour
from spade.message import Message

from Models.LightStatus import LightStatus


class EmergencyCarAgent(Agent):
    def __init__(self, jid, password, environment):
        super().__init__(jid, password)
        self.environment = environment
        self.id = jid
        self.password = password

        self.guid = uuid.uuid4()

        self.car_at_traffic_light = False

        # Adiciona o veiculo ao ambiente
        self.car_obj = self.environment.add_emergency_car(self.id)

    async def setup(self):
        class CyclicBehav(CyclicBehaviour):
            def __init__(self, agent):
                super().__init__()
                self.agent = agent

                # Guarda as variáveis do agente no behaviour
                self.id = self.agent.id
                self.car = self.agent.car_obj
                self.env = self.agent.environment
                self.is_msg_sent = False

            async def run(self):
                # Veiculo de emergencia termina quando sai do mapa (is_car_done)
                if self.car.sprites()[0].is_car_done():
                    print("EMERGENCY DONE")
                    self.kill()

                await self.move()

                # Atualiza o objeto no mapa
                self.car.sprites()[0].update()

            async def move(self):
                # Verifica se o veiculo está num semáforo
                is_tl_collided, tl_id = self.env.collision_traffic_light(self.car.sprites()[0])

                # Caso esteja no semáforo valida o seu estado
                if is_tl_collided and self.env.get_traffic_light_status(tl_id) == LightStatus.RED:
                    # Caso esteja vermelho para o veiculo
                    self.car.sprites()[0].stop_car()

                    current_awaiting_time = 0
                    if self.agent.guid in self.env.emergency_cars_awaiting_time:
                        current_awaiting_time = self.env.emergency_cars_awaiting_time[self.agent.guid]

                    self.env.emergency_cars_awaiting_time[self.agent.guid] = current_awaiting_time + 1

                    # Envia um pedido ao Semáforo para ficar verde
                    if not self.is_msg_sent:
                        msg_behav = SendMsgBehav(self.env.get_traffic_light_jid_by_id(tl_id), tl_id)
                        self.agent.add_behaviour(msg_behav)
                        self.is_msg_sent = True

                    # No caso do semáforo não conseguir mudar o seu estado por causa do acidente, ao fim de algum tempo o veiculo vai tomar nova direção
                    if self.env.emergency_cars_awaiting_time[self.agent.guid] > 150 and not self.car.sprites()[
                        0].is_car_changing_direction():
                        self.car.sprites()[0].activate_changing_direction()
                        self.car.sprites()[0].change_direction(str(tl_id).split("_")[3])
                        self.is_msg_sent = False
                        self.env.emergency_cars_awaiting_time[self.agent.guid] = 0
                else:
                    self.env.emergency_cars_awaiting_time[self.agent.guid] = 0

                    # Estando o semáforo verde avança
                    self.car.sprites()[0].disable_changing_direction()
                    self.car.stopped_at_tl_id = False
                    self.is_msg_sent = False

                    if self.env.collision_sprite(self.car.sprites()[0]):
                        self.car.sprites()[0].fires_car()
                        self.car.sprites()[0].activate_turning()
                        self.car.sprites()[0].flag_car_is_turning(True)
                    else:
                        self.car.sprites()[0].flag_car_is_turning(False)
                        self.car.sprites()[0].fires_car()

        behaviour = CyclicBehav(self)
        self.add_behaviour(behaviour)

        class SendMsgBehav(OneShotBehaviour):
            def __init__(self, tl_jid, tl_id):
                super().__init__()
                self.tl_jid = tl_jid
                self.tl_id = tl_id

            # Envia mensagem para o agente Semáforo no qual o veiculo está parado a pedir que altere o seu estado para verde
            async def run(self):
                print("EMERGENCY REQUESTING GREEN LIGHT")
                msg = Message(to=self.tl_jid)
                msg.set_metadata("performative", "request")
                msg.set_metadata("action", "change_status")
                msg.set_metadata("traffic_light", self.tl_id)
                msg.body = "Emergency Vehicle Requesting Green Light"

                await self.send(msg)
                print("Request Made - Msg Sent")

                self.exit_code = "Job Finished!"