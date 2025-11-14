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
                # Antes de colidir com o TL, tentar preempção por aproximação
                try:
                    await self.try_preempt_on_approach()
                except Exception:
                    # Em caso de qualquer erro na deteção, seguir fluxo normal
                    pass

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

                    # Envia um pedido (ao Coordenador se existir; caso contrário, diretamente ao Semáforo) para ficar verde
                    if not self.is_msg_sent:
                        msg_behav = SendMsgBehav(self.env, tl_id)
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
            def __init__(self, env, tl_id):
                super().__init__()
                self.env = env
                self.tl_id = tl_id

            # Envia mensagem para o agente Semáforo no qual o veiculo está parado a pedir que altere o seu estado para verde
            async def run(self):
                print("EMERGENCY REQUESTING GREEN LIGHT")
                # Se houver coordenador ativo, enviar pedido ao coordenador;
                # caso contrário, enviar diretamente ao agente do semáforo atual
                if getattr(self.env, "coordinator_enabled", False) and getattr(self.env, "coordinator_jid", None):
                    to_jid = self.env.coordinator_jid
                    action = "emergency_request"
                else:
                    to_jid = self.env.get_traffic_light_jid_by_id(self.tl_id)
                    action = "change_status"

                msg = Message(to=to_jid)
                msg.set_metadata("performative", "request")
                msg.set_metadata("action", action)
                msg.set_metadata("traffic_light", self.tl_id)
                msg.body = "Emergency Vehicle Requesting Green Light"

                await self.send(msg)
                print("Request Made - Msg Sent")

                self.exit_code = "Job Finished!"

        # ------------------------- AUX/APPROACH LOGIC -------------------------
        async def try_preempt_on_approach(self):
            """
            Se existir um semáforo à frente (na mesma linha/faixa) dentro de uma
            distância de aproximação e ele estiver vermelho, envia pedido de
            prioridade antes de o veículo parar.
            """
            car_sprite = self.car_obj.sprites()[0]
            car_x, car_y, angle = car_sprite.get_car_position()

            # Parâmetros de deteção (px)
            APPROACH_DISTANCE = 150
            LATERAL_TOL = 60

            side = _side_from_angle(angle)
            if not side:
                return

            candidate = None
            best_ahead_dist = None

            for tl_id, tl_obj in self.environment.traffic_lights_objects.items():
                parts = str(tl_id).split("_")
                if len(parts) < 4:
                    continue
                side_letter = parts[2]  # t, b, l, r

                if side_letter != side:
                    continue

                tl_cx, tl_cy = tl_obj.rect.centerx, tl_obj.rect.centery

                # Determina se o TL está "à frente" e dentro dos limiares
                ahead = False
                axis_dist = None

                if side == 'b':  # a subir (angle ~0): TL à frente tem y < carro
                    axis_dist = car_y - tl_cy
                    ahead = 0 < axis_dist <= APPROACH_DISTANCE and abs(car_x - tl_cx) <= LATERAL_TOL
                elif side == 't':  # a descer (angle ~180): TL à frente tem y > carro
                    axis_dist = tl_cy - car_y
                    ahead = 0 < axis_dist <= APPROACH_DISTANCE and abs(car_x - tl_cx) <= LATERAL_TOL
                elif side == 'l':  # a ir para a direita (angle ~-90): TL à frente tem x > carro
                    axis_dist = tl_cx - car_x
                    ahead = 0 < axis_dist <= APPROACH_DISTANCE and abs(car_y - tl_cy) <= LATERAL_TOL
                elif side == 'r':  # a ir para a esquerda (angle ~90): TL à frente tem x < carro
                    axis_dist = car_x - tl_cx
                    ahead = 0 < axis_dist <= APPROACH_DISTANCE and abs(car_y - tl_cy) <= LATERAL_TOL

                if not ahead:
                    continue

                # Apenas interessa se está vermelho neste momento
                try:
                    if self.environment.get_traffic_light_status(tl_id) != LightStatus.RED:
                        continue
                except Exception:
                    continue

                # Escolher o mais próximo ao longo do eixo
                if best_ahead_dist is None or axis_dist < best_ahead_dist:
                    best_ahead_dist = axis_dist
                    candidate = tl_id

            if candidate and not self.is_msg_sent:
                # Envia pedido de preempção igual ao de paragem (via coordenador, se existir)
                msg_behav = SendMsgBehav(self.environment, candidate)
                self.add_behaviour(msg_behav)
                self.is_msg_sent = True


def _side_from_angle(angle):
    """
    Mapeia o ângulo de movimento para a "side" do TL que o veículo enfrenta.
    0 (subir)  -> 'b'
    180 (descer) -> 't'
    -90 (direita) -> 'l'
    90 (esquerda) -> 'r'
    Usa tolerância para ângulos próximos.
    """
    # Normalizar ângulo para [-180, 180]
    a = angle
    while a > 180:
        a -= 360
    while a <= -180:
        a += 360

    def near(x):
        return abs(a - x) <= 30  # tolerância de 30º

    if near(0):
        return 'b'
    if near(180) or near(-180):
        return 't'
    if near(-90):
        return 'l'
    if near(90):
        return 'r'
    return None