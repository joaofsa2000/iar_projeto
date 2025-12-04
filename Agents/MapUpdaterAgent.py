import asyncio
from datetime import datetime, timedelta
import random
import time
import uuid

from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour, CyclicBehaviour, OneShotBehaviour
from spade.message import Message
from spade.template import Template

from Agents.EmergencyCarAgent import EmergencyCarAgent
from Agents.CarAgent import CarAgent


class MapUpdaterAgent(Agent):
    def __init__(self, jid, password, environment, initial_car_count=15):
        super().__init__(jid, password)
        self.environment = environment
        self.id = jid
        
        # Counter for spawning new cars with unique IDs
        self.next_car_id = initial_car_count  # Start after initial cars
        self.next_emergency_id = 1
        
        # List of all registered agent JIDs for broadcasting
        self.registered_agents = []
        
        # Traffic light agent JIDs
        self.traffic_light_jids = [
            "semaforos_1@localhost",
            "semaforos_2@localhost",
            "semaforos_3@localhost",
            "semaforos_4@localhost",
            "semaforos_5@localhost",
            "semaforos_6@localhost",
        ]

    async def setup(self):
        print(f"[MAP UPDATER {self.jid}] Agente central iniciado")

        # Comportamento periódico para atualizar o mapa pygame
        class MapUpdateBehaviour(PeriodicBehaviour):
            async def run(self):
                self.agent.environment.update_map()

            async def on_end(self):
                await self.agent.stop()

        start_at = datetime.now() + timedelta(seconds=2)
        period = MapUpdateBehaviour(period=0, start_at=start_at)
        self.add_behaviour(period)

        # Comportamento periódico (2s) para criar carros normais baseado na densidade de tráfego
        class CarSpawnBehaviour(PeriodicBehaviour):
            async def run(self):
                # Check if we should spawn a new car based on traffic density
                if self.agent.environment.should_spawn_car():
                    car_id = self.agent.next_car_id
                    self.agent.next_car_id += 1
                    
                    try:
                        new_car = CarAgent(f"carro_{car_id}@localhost", "pass", self.agent.environment)
                        await new_car.start(auto_register=True)
                        print(f"[MAP UPDATER] Novo carro spawned: carro_{car_id}")
                    except Exception as e:
                        print(f"[MAP UPDATER] Erro ao criar carro: {e}")

            async def on_end(self):
                pass  # Don't stop the agent when this ends

        car_spawn_interval = 1  # Check every 1 second (faster spawning)
        start_at = datetime.now() + timedelta(seconds=3)  # Start after initial setup
        car_spawn_period = CarSpawnBehaviour(period=car_spawn_interval, start_at=start_at)
        self.add_behaviour(car_spawn_period)

        # Comportamento periódico (15s) para criar um veículo de emergência
        class EmergencySpawnBehaviour(PeriodicBehaviour):
            async def run(self):
                emergency_id = self.agent.next_emergency_id
                self.agent.next_emergency_id += 1
                
                print(f"[MAP UPDATER {self.agent.jid}] Criando veículo de emergência #{emergency_id}")
                try:
                    emergency_car = EmergencyCarAgent(f"emergencia_carro_{emergency_id}@localhost", "pass", self.agent.environment)
                    await emergency_car.start(auto_register=True)
                except Exception as e:
                    print(f"[MAP UPDATER] Erro ao criar veículo emergência: {e}")

            async def on_end(self):
                pass  # Don't stop the agent when this ends

        emergency_interval = 15  # Every 15 seconds
        start_at = datetime.now() + timedelta(seconds=emergency_interval)
        period = EmergencySpawnBehaviour(period=emergency_interval, start_at=start_at)
        self.add_behaviour(period)

        # Comportamento periódico (25s) para análise de congestionamento
        class CongestionAnalysisBehaviour(PeriodicBehaviour):
            async def run(self):
                print(f"[MAP UPDATER {self.agent.jid}] Analisando congestionamento...")

                # Inicializa contadores para cada cruzamento
                CROSSES = {
                    "top_left": 0,
                    "top_mid": 0,
                    "top_right": 0,
                    "bottom_left": 0,
                    "bottom_mid": 0,
                    "bottom_right": 0
                }

                # Conta o número de carros parados em cada cruzamento
                cars_stopped = self.agent.environment.cars_stopped_at_tl
                for x in cars_stopped:
                    cross = x[:-4]
                    if cross in CROSSES:
                        CROSSES[cross] += len(self.agent.environment.cars_stopped_at_tl[x])

                max_cross = max(CROSSES, key=lambda k: CROSSES[k])
                vehicle_count = max(CROSSES.values())

                print(
                    f"[MAP UPDATER {self.agent.jid}] Cruzamento mais congestionado: {max_cross} ({vehicle_count} veículos)")

                # Calculate congestion levels for all intersections
                for intersection_id in CROSSES:
                    self.agent.environment.calculate_congestion_level(intersection_id)

                # High congestion threshold
                if vehicle_count > 5:
                    print(f"[MAP UPDATER {self.agent.jid}] ALERTA DE CONGESTIONAMENTO em {max_cross}!")
                    
                    # FIPA REQUEST PROTOCOL - Solicitar aos semáforos para ajustar tempos
                    await self.request_traffic_adjustment(max_cross, vehicle_count)
                    
                    # Broadcast alert to all agents
                    await self.broadcast_alert(f"CONGESTION_ALERT: High traffic at {max_cross} ({vehicle_count} vehicles)")

            async def request_traffic_adjustment(self, crossing, vehicle_count):
                """Envia pedido aos semáforos para ajustar ciclos (FIPA Request Protocol)"""
                # Mapeia cruzamento para agente de semáforo
                crossing_to_agent = {
                    "top_left": "semaforos_4@localhost",
                    "top_mid": "semaforos_5@localhost",
                    "top_right": "semaforos_6@localhost",
                    "bottom_left": "semaforos_1@localhost",
                    "bottom_mid": "semaforos_2@localhost",
                    "bottom_right": "semaforos_3@localhost"
                }

                tl_jid = crossing_to_agent.get(crossing)
                if not tl_jid:
                    return

                conv_id = str(uuid.uuid4())

                msg = Message(to=tl_jid)
                msg.set_metadata("performative", "request")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", conv_id)
                msg.set_metadata("action", "adjust_timing")
                msg.body = f"CONGESTION_ALERT: {vehicle_count} vehicles at {crossing}. Request extended green phase."

                await self.send(msg)
                print(f"[MAP UPDATER {self.agent.jid}] REQUEST enviado para {tl_jid} (conv-id: {conv_id})")

            async def broadcast_alert(self, alert_message: str):
                """Broadcast an alert message to all traffic light agents."""
                conv_id = str(uuid.uuid4())
                
                for tl_jid in self.agent.traffic_light_jids:
                    msg = Message(to=tl_jid)
                    msg.set_metadata("performative", "inform")
                    msg.set_metadata("protocol", "fipa-inform")
                    msg.set_metadata("conversation-id", conv_id)
                    msg.body = alert_message
                    
                    await self.send(msg)

            async def on_end(self):
                await self.agent.stop()

        congestion_interval = 25
        start_at = datetime.now() + timedelta(seconds=congestion_interval)
        period = CongestionAnalysisBehaviour(period=congestion_interval, start_at=start_at)
        self.add_behaviour(period)

        # Comportamento para receber respostas dos semáforos
        class ReceiveTrafficResponseBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)

                if msg and msg.get_metadata("protocol") == "fipa-request":
                    performative = msg.get_metadata("performative")
                    conv_id = msg.get_metadata("conversation-id")

                    if performative == "agree":
                        print(f"[MAP UPDATER {self.agent.jid}] AGREE recebido de {msg.sender}")
                        print(f"[MAP UPDATER {self.agent.jid}] Semáforo aceitou ajustar tempos")

                    elif performative == "inform":
                        print(f"[MAP UPDATER {self.agent.jid}] INFORM recebido de {msg.sender}")
                        print(f"[MAP UPDATER {self.agent.jid}] Resultado: {msg.body}")

                    elif performative == "refuse":
                        print(f"[MAP UPDATER {self.agent.jid}] REFUSE recebido de {msg.sender}")
                        print(f"[MAP UPDATER {self.agent.jid}] Motivo: {msg.body}")

                    elif performative == "failure":
                        print(f"[MAP UPDATER {self.agent.jid}] FAILURE recebido de {msg.sender}")
                        print(f"[MAP UPDATER {self.agent.jid}] Erro: {msg.body}")

        template = Template()
        template.set_metadata("protocol", "fipa-request")
        self.add_behaviour(ReceiveTrafficResponseBehaviour(), template)

        # ============================================================
        # FIPA INFORM PROTOCOL - Broadcast de Alertas Periódicos
        # ============================================================
        class BroadcastAlertBehaviour(PeriodicBehaviour):
            """Envia alertas periódicos sobre o estado do sistema"""

            async def run(self):
                # Coleta estatísticas do sistema
                total_cars = len(self.agent.environment.car_positions)
                total_stopped = sum(len(cars) for cars in self.agent.environment.cars_stopped_at_tl.values())
                avg_speed = self.agent.environment.get_average_speed()

                # Determine system status
                if total_stopped > 10:
                    status = "HIGH_CONGESTION"
                elif total_stopped > 5:
                    status = "MODERATE_TRAFFIC"
                else:
                    status = "NORMAL"

                alert_msg = f"SYSTEM_STATUS: {status} | Vehicles: {total_cars} | Stopped: {total_stopped} | Avg Speed: {avg_speed:.1f}"

                print(f"[MAP UPDATER {self.agent.jid}] Broadcasting: {alert_msg}")

                # Broadcast to all traffic light agents
                await self.broadcast_to_traffic_lights(alert_msg)

            async def broadcast_to_traffic_lights(self, alert_message: str):
                """Broadcast an alert message to all traffic light agents."""
                conv_id = str(uuid.uuid4())
                
                for tl_jid in self.agent.traffic_light_jids:
                    msg = Message(to=tl_jid)
                    msg.set_metadata("performative", "inform")
                    msg.set_metadata("protocol", "fipa-inform")
                    msg.set_metadata("conversation-id", conv_id)
                    msg.body = alert_message
                    
                    await self.send(msg)

        # Activate broadcast behavior every 30 seconds
        broadcast_interval = 30
        start_at = datetime.now() + timedelta(seconds=broadcast_interval)
        self.add_behaviour(BroadcastAlertBehaviour(period=broadcast_interval, start_at=start_at))
