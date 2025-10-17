# CarAgent.py

from datetime import datetime, timedelta
import math
import time
import pygame

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

from Models.LightStatus import LightStatus


class CarAgent(Agent):
    def __init__(self, jid, password, environment):
        super().__init__(jid, password)
        self.environment = environment

        self.id = jid

        self.car_at_traffic_light = False
        self.car_obj = self.environment.add_car(self.id)

    async def setup(self):
        class CyclicBehav(CyclicBehaviour):
            def __init__(self, agent):
                super().__init__()
                self.agent = agent

                # Guarda referências
                self.id = self.agent.id
                self.car = self.agent.car_obj
                self.env = self.agent.environment

            async def run(self):
                # Verifica colisões com outros carros
                # Apenas move o carro se não houver colisão
                if not await self.is_colliding():
                    await self.move()
                    # Atualiza a posição do carro no ambiente
                    self.env.update_car_position(self.id, self.car.sprites()[0].get_car_position())
                else:
                    # Se houver colisão, para o carro
                    self.car.sprites()[0].stop_car()

                # Atualiza o estado do carro no mapa
                self.car.sprites()[0].update()

            async def move(self):
                # Verifica se o carro colidiu
                is_tl_collided, tl_id = self.env.collision_traffic_light(self.car.sprites()[0])

                #semáforo vermelho -> carro parado
                if is_tl_collided and self.env.get_traffic_light_status(tl_id) == LightStatus.RED:
                    self.car.sprites()[0].stop_car()
                    self.car.stopped_at_tl_id = tl_id
                    # Inicia contagem do tempo de espera no semáforo
                    self.car.stopped_at_tl_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    await self.set_cars_at_traffic_light(tl_id)
                else:
                    if self.env.collision_sprite(self.car.sprites()[0]):
                        self.car.sprites()[0].fires_car()
                        self.car.sprites()[0].activate_turning()
                        self.car.sprites()[0].flag_car_is_turning(True)
                    else:
                        self.car.sprites()[0].flag_car_is_turning(False)
                        self.car.sprites()[0].fires_car()

                    # Termina espera no semáforo
                    if hasattr(self.car, 'stopped_at_tl_start_time') and self.car.stopped_at_tl_start_time:
                        await self.set_cars_stopped_times()

                    self.car.stopped_at_tl_id = False

            # Guarda os tempos de espera dos carros nos semáforos
            async def set_cars_stopped_times(self):
                difference = self.calc_time_difference(self.car.stopped_at_tl_start_time, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                if difference:
                    self.env.cars_stopped_times.append((self.car.stopped_at_tl_id, self.car.sprites()[0].id, difference))
                self.car.stopped_at_tl_start_time = False

            # Calcula a diferença de tempo entre início e fim
            def calc_time_difference(self, start_time, end_time):
                time_format = "%Y-%m-%d %H:%M:%S"
                start = datetime.strptime(start_time, time_format)
                end = datetime.strptime(end_time, time_format)
                difference = end - start

                return str(difference) if difference > timedelta(0) else False

            # Marca no ambiente os carros que estão parados em semáforos
            async def set_cars_at_traffic_light(self, tl_id):
                # Inicializa a lista se ainda não existir para este semáforo
                if tl_id not in self.env.cars_stopped_at_tl:
                    self.env.cars_stopped_at_tl[tl_id] = []

                # Adiciona o carro à lista de parados no semáforo
                if self.id not in self.env.cars_stopped_at_tl[tl_id]:
                    self.env.cars_stopped_at_tl[tl_id].append(self.id)

            # Verifica colisão com outros carros
            async def is_colliding(self):
                angle = self.car.sprites()[0].angle
                coordinates = self.env.car_positions[self.id]

                # Determina intervalo de colisão baseado no ângulo do carro
                limit = await self.get_value_by_angle(angle)

                if (abs(angle / 90) % 2) == 0:
                    value_to_check = coordinates[1] + limit
                    static_value_to_check = coordinates[0]
                else:
                    value_to_check = coordinates[0] + limit
                    static_value_to_check = coordinates[1]

                # Compara posição do carro com todos os outros no ambiente
                for env_car in self.env.car_positions.keys():
                    if env_car == self.id:
                        continue

                    if (abs(angle / 90) % 2) == 0:
                        other_value = self.env.car_positions[env_car][1]
                        other_static = self.env.car_positions[env_car][0]
                    else:
                        other_value = self.env.car_positions[env_car][0]
                        other_static = self.env.car_positions[env_car][1]

                    # Verifica sobreposição de coordenadas
                    if (other_value - 1 <= value_to_check <= other_value + 1) and (other_static - 7 <= static_value_to_check <= other_static + 7):
                        if hasattr(self.env.get_car_by_id(env_car), 'stopped_at_tl_id'):
                            tl_id = self.env.get_car_by_id(env_car).stopped_at_tl_id
                            if tl_id:
                                self.car.stopped_at_tl_id = tl_id
                                await self.set_cars_at_traffic_light(tl_id)

                        return True

                return False

            # Retorna o offset do carro dependendo do ângulo
            async def get_value_by_angle(self, angle):
                if angle in [0, 90, 360, -270, -360]:
                    return -38
                elif angle in [180, 270, -90, -180]:
                    return 38
                else:
                    return 0

        behaviour = CyclicBehav(self)
        self.add_behaviour(behaviour)
