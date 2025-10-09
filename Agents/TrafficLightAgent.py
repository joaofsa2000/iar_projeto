#TrafficLigthAgent.py

import asyncio
from datetime import datetime, timedelta
import math
import time
import pygame

from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from Models.LightStatus import LightStatus


class TrafficLightAgent(Agent):
    def __init__(self, jid, password, traffic_lights, environment):
        super().__init__(jid, password)
        self.environment = environment

        self.traffic_lights = []
        
        #Criação de todos os 9 semáforos do cruzamento, guardando os elemntos no ambiente
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_b_l", traffic_lights.bottom_tl.left_tl.coordinate, traffic_lights.bottom_tl.left_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_b_c", traffic_lights.bottom_tl.center_tl.coordinate, traffic_lights.bottom_tl.center_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_b_r", traffic_lights.bottom_tl.right_tl.coordinate, traffic_lights.bottom_tl.right_tl.angle))
 
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_l_l", traffic_lights.left_tl.left_tl.coordinate, traffic_lights.left_tl.left_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_l_c", traffic_lights.left_tl.center_tl.coordinate, traffic_lights.left_tl.center_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_l_r", traffic_lights.left_tl.right_tl.coordinate, traffic_lights.left_tl.right_tl.angle))

        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_t_l", traffic_lights.top_tl.left_tl.coordinate, traffic_lights.top_tl.left_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_t_c", traffic_lights.top_tl.center_tl.coordinate, traffic_lights.top_tl.center_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_t_r", traffic_lights.top_tl.right_tl.coordinate, traffic_lights.top_tl.right_tl.angle))
 
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_r_l", traffic_lights.right_tl.left_tl.coordinate, traffic_lights.right_tl.left_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_r_c", traffic_lights.right_tl.center_tl.coordinate, traffic_lights.right_tl.center_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_r_r", traffic_lights.right_tl.right_tl.coordinate, traffic_lights.right_tl.right_tl.angle))

    async def setup(self):
        class PeriodicBehav(PeriodicBehaviour):
            async def run(self):
                # Coloca todos a vermelho antes de abrir os verdes
                for tl in self.agent.traffic_lights:
                    tl.change_status(LightStatus.RED)
                    self.agent.environment.update_traffic_light_status(tl.id, LightStatus.RED)

                # Cria uma lista com todos os semaforos que têm carros parados deste agente
                new_list = {}
                for tl in self.agent.traffic_lights:
                    if (tl.id in self.agent.environment.cars_stopped_at_tl
                            and len(self.agent.environment.cars_stopped_at_tl[tl.id]) > 0):
                        new_list[tl.id] = self.agent.environment.cars_stopped_at_tl[tl.id]

                # Ordenar a lista de carros parados nos semaforos
                sorted_tuples = sorted(new_list.items(), key=lambda x: len(x[1]), reverse=True)
                lista_ordenada = dict(sorted_tuples)

                if len(lista_ordenada) > 0:
                    tl_to_open = list(lista_ordenada.keys())[0]
                    blocked_turn = ""

                    #No caso do semáforo com mais carros estar com o caminho bloqueado por causa do acidente ele avança para o seguinte com mais carros
                    for tl in lista_ordenada.keys():
                        if not self.agent.environment.map_crash:
                            tl_to_open = tl
                            break

                        blocked_turn = self.agent.environment.get_blocked_turn(tl, self.agent.environment.crash_location)
                        
                        if blocked_turn and blocked_turn == str(tl).split("_")[3]:
                            continue
                        else:
                            tl_to_open = tl
                            break

                    # cria lista para abrir todos os semaforos que tiverem carros ( no mesmo sentido )
                    new_tls = []
                    blocked_turn = self.agent.environment.get_blocked_turn(tl_to_open, self.agent.environment.crash_location)

                    #Ao abrir um determinado semafóro ele automaticamente abre também os semafóros das faixas do lado, no vaso de estes terem carros
                    for direction in ['l', 'c', 'r']:
                        if direction == blocked_turn: continue

                        new_tl = tl_to_open[:-1] + direction
                        if (new_tl in self.agent.environment.cars_stopped_at_tl
                                and len(self.agent.environment.cars_stopped_at_tl[new_tl]) > 0):
                            new_tls.append(new_tl)
                    
                    #Muda o estado do semáforo para verde no mapa e no ambiente
                    for new_tl in new_tls:
                        tl = self.agent.environment.traffic_lights_objects[str(new_tl)]
                        tl.change_status(LightStatus.GREEN)
                        self.agent.environment.update_traffic_light_status(tl.id, LightStatus.GREEN)
                        self.agent.environment.cars_stopped_at_tl[tl.id].clear()

                lista_ordenada.clear()

        start_at = datetime.now() + timedelta(seconds=2)
        period = PeriodicBehav(period=10, start_at=start_at)
        self.add_behaviour(period)
        
        #Comportamento responsável por receber mensagens dos veiculos de emergencia a pedir para mudar o estado para verde
        class ReceiveMsgBehav(CyclicBehaviour):
            def __init__(self):
                super().__init__()

            async def run(self):                
                msg = await self.receive(timeout=60)
                if msg:
                    if msg.metadata["action"] == "change_status":
                        #Coloca todos os semáforos do cruzamento a vermelho
                        for tl in self.agent.traffic_lights:
                            tl.change_status(LightStatus.RED)
                            self.agent.environment.update_traffic_light_status(tl.id, LightStatus.RED)

                        #Guarda o semáforo que o veiculo de emergencia está a pedir para abrir
                        tl = self.agent.environment.traffic_lights_objects[str(msg.metadata["traffic_light"])]
                        
                        #Verifica se pode abrir o semáforo pedido ou se existe algum acidente que impossibilite a mudança de estado
                        if self.agent.environment.map_crash:
                            blocked_turn = self.agent.environment.get_blocked_turn(tl.id, self.agent.environment.crash_location)
                            
                            if blocked_turn and blocked_turn == str(tl.id).split("_")[3]: 
                                return

                        #Altera o estado do semáforo pedido para verde
                        tl.change_status(LightStatus.GREEN)
                        self.agent.environment.update_traffic_light_status(tl.id, LightStatus.GREEN)
                        if tl.id in self.agent.environment.cars_stopped_at_tl: self.agent.environment.cars_stopped_at_tl[tl.id].clear()
        
        template = Template()
        template.set_metadata("performative", "request")
        self.add_behaviour(ReceiveMsgBehav(), template)