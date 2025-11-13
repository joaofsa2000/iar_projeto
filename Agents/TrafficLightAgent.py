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
        # O ciclo de decisão local foi desativado: o Coordenador passa a controlar os semáforos.
        # Este agente agora executa comandos vindos do Coordenador.

        # Comportamento: recebe comandos do Coordenador para definir fases ou colocar tudo a vermelho
        class ReceiveCoordinatorCommandsBehav(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=60)
                if not msg or not msg.metadata:
                    return

                action = msg.metadata.get("action")
                if action == "all_red":
                    # Coloca todos os semáforos deste cruzamento a vermelho
                    for tl in self.agent.traffic_lights:
                        tl.change_status(LightStatus.RED)
                        self.agent.environment.update_traffic_light_status(tl.id, LightStatus.RED)
                    return

                if action == "set_phase":
                    # Espera metadado 'open_tls' com lista CSV de ids a abrir
                    open_csv = msg.metadata.get("open_tls", "")
                    open_list = [x.strip() for x in open_csv.split(",") if x.strip()]

                    # Primeiro, tudo vermelho
                    for tl in self.agent.traffic_lights:
                        tl.change_status(LightStatus.RED)
                        self.agent.environment.update_traffic_light_status(tl.id, LightStatus.RED)

                    # Depois, abrir os indicados
                    for open_id in open_list:
                        if open_id in self.agent.environment.traffic_lights_objects:
                            tl = self.agent.environment.traffic_lights_objects[open_id]
                            tl.change_status(LightStatus.GREEN)
                            self.agent.environment.update_traffic_light_status(tl.id, LightStatus.GREEN)
                            if tl.id in self.agent.environment.cars_stopped_at_tl:
                                self.agent.environment.cars_stopped_at_tl[tl.id].clear()

        # Aceita mensagens inform do Coordenador
        coord_template = Template()
        coord_template.set_metadata("performative", "inform")
        self.add_behaviour(ReceiveCoordinatorCommandsBehav(), coord_template)
        
        #Comportamento responsável por receber mensagens diretas dos veiculos de emergencia (legado)
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