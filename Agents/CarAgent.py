#CarAgent.py

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

        #Adiciona o carro no ambiente e guarda o objeto
        self.car_obj = self.environment.add_car(self.id)

    async def setup(self):
        class CyclicBehav(CyclicBehaviour):
            def __init__(self, agent):
                super().__init__()
                self.agent = agent

                #Guarda as variáveis do agente no behaviour
                self.id = self.agent.id
                self.car = self.agent.car_obj
                self.env = self.agent.environment

            async def run(self):
                #Verifica se o carro está a colidir com outros carros
                #Só move se não existir colisão
                if not await self.is_colliding():
                    await self.move()

                    #Atualiza a posição do carro no ambiente
                    self.env.update_car_position(self.id, self.car.sprites()[0].get_car_position())
                else:
                    #Em caso de colisão para o carro
                    self.car.sprites()[0].stop_car()
                
                #Atualiza o objeto no mapa
                self.car.sprites()[0].update()

            async def move(self):
                #Verifica se o carro está num semafóro
                is_tl_collided, tl_id = self.env.collision_traffic_light(self.car.sprites()[0])

                #Caso esteja no semáforo, valida o seu estado e só avança caso esteja verde
                if is_tl_collided and self.env.get_traffic_light_status(tl_id) == LightStatus.RED:
                    self.car.sprites()[0].stop_car()

                    #Guarda no ambiente que o carro está parado no semáforo
                    self.car.stopped_at_tl_id = tl_id

                    #Inicia a contagem de tempo da métrica "tempo de espera" do carro no semáforo
                    self.car.stopped_at_tl_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    await self.set_cars_at_traffic_light(tl_id)
                else:
                    #Método pygame de viragem do carro no cruzamento
                    if self.env.collision_sprite(self.car.sprites()[0]):
                        self.car.sprites()[0].fires_car()
                        self.car.sprites()[0].activate_turning()
                        self.car.sprites()[0].flag_car_is_turning(True)
                    else:
                        self.car.sprites()[0].flag_car_is_turning(False)
                        self.car.sprites()[0].fires_car()

                    #Finaliza a contagem de tempo da métrica "tempo de espera" do carro no semáforo e guarda
                    if hasattr(self.car, 'stopped_at_tl_start_time'):
                        if self.car.stopped_at_tl_start_time:
                            await self.set_cars_stopped_times()

                    self.car.stopped_at_tl_id = False

            #Guarda os tempos de espera de cada carro nos semáforos
            async def set_cars_stopped_times(self):
                difference = self.calc_time_diference(self.car.stopped_at_tl_start_time, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                if difference:
                    self.env.cars_stopped_times.append((self.car.stopped_at_tl_id, self.car.sprites()[0].id, difference))
                self.car.stopped_at_tl_start_time = False

            #Faz o calculo do tempo de espera
            def calc_time_diference(self, start_time, end_time):
                format = "%Y-%m-%d %H:%M:%S"
                start = datetime.strptime(start_time, format)
                end = datetime.strptime(end_time, format)
                difference = end - start

                return str(difference) if difference > timedelta(0) else False

            #Marca no ambiente os carros que estão parados em semáforos
            async def set_cars_at_traffic_light(self, tl_id):
                # Inicializa a contagem para a chave tl_id se ela ainda não existir
                if tl_id not in self.env.cars_stopped_at_tl:
                    self.env.cars_stopped_at_tl[tl_id] = []

                # Incrementa com os carros parados no semáforo
                if self.id not in self.env.cars_stopped_at_tl[tl_id]:
                    self.env.cars_stopped_at_tl[tl_id].append(self.id)

            #Verifica a colisão de um carro com outros
            async def is_colliding(self):  
                angle = self.car.sprites()[0].angle
                coordinates = self.env.car_positions[self.id]
                
                #Obtém o intevalo entre carros pelo angulo em que o carro se encontra
                limit = await self.get_value_by_angle(angle)

                value_to_check = 0
                static_value_to_check = 0

                #Se o angulo for par tem que olhar para a coordenada y
                #Se o angulo for impar tem que olhar para a coordenada x
                if (abs(angle / 90) % 2) == 0:
                    value_to_check = coordinates[1] + limit
                    static_value_to_check = coordinates[0] 
                else:
                    value_to_check = coordinates[0] + limit
                    static_value_to_check = coordinates[1] 

                #Ciclo por todas as posições dos carros do ambiente
                #Caso exista sobreposião de coordenadas respeitando o intervalo definido anteriormente retorna Tue (colisão)
                #Caso contrário retorna False (não colisão)
                for env_car in self.env.car_positions.keys():
                    if env_car == self.id: continue

                    other_car_value_to_check = 0
                    other_static_value_to_check = 0
                    if (abs(angle / 90) % 2) == 0:
                        other_car_value_to_check = self.env.car_positions[env_car][1]
                        other_static_value_to_check = self.env.car_positions[env_car][0]
                    else:
                        other_car_value_to_check = self.env.car_positions[env_car][0]
                        other_static_value_to_check = self.env.car_positions[env_car][1]

                    if (other_car_value_to_check - 1 <=  value_to_check and value_to_check <= other_car_value_to_check + 1) and (other_static_value_to_check - 7 <=  static_value_to_check and static_value_to_check <= other_static_value_to_check + 7):
                        if hasattr(self.env.get_car_by_id(env_car), 'stopped_at_tl_id'):
                            tl_id = self.env.get_car_by_id(env_car).stopped_at_tl_id
                            if tl_id:
                                self.car.stopped_at_tl_id = tl_id
                                await self.set_cars_at_traffic_light(tl_id)

                        return True

                return False

            #Retorna o intervalo offset que cada carro pode ter do outro dependendo do angulo
            async def get_value_by_angle(self, angle):
                if angle == 0:
                    return -38
                elif angle == 90:
                    return -38
                elif angle == 180:
                    return 38
                elif angle == 270:
                    return 38
                elif angle == 360:
                    return -38
                elif angle == -90:
                    return 38
                elif angle == -180:
                    return 38
                elif angle == -270:
                    return -38
                elif angle == -360:
                    return -38
                else:
                    #if angle > 360 or angle < -360: print(angle)
                    return 0

        behaviour = CyclicBehav(self)
        self.add_behaviour(behaviour)
