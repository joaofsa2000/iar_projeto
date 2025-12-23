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
    def __init__(self, jid, password, environment, initial_car_count=15, debug_mode=False):
        super().__init__(jid, password)
        self.environment = environment
        self.id = jid
        self.debug_mode = debug_mode  # Debug mode: only spawn 2 cars on same lane
        
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

        # Comportamento periódico para criar carros normais baseado na densidade de tráfego
        # Uses simulation time, not real time, so it scales with time speed
        # DISABLED in debug mode
        if not self.debug_mode:
            class CarSpawnBehaviour(CyclicBehaviour):
                def __init__(self, agent):
                    super().__init__()
                    self.agent = agent
                    self.last_spawn_time = None  # Store last spawn time in simulation time
                    self.spawn_interval_sim = 0.5  # Spawn check interval in simulation seconds
                
                async def run(self):
                    # Use simulation time, not real time
                    current_sim_time = self.agent.environment.simulation_time
                    
                    # Initialize last_spawn_time on first run
                    if self.last_spawn_time is None:
                        self.last_spawn_time = current_sim_time
                        # Very short initial sleep, adjusted by simulation speed
                        base_sleep = 0.01
                        sim_speed = max(1, self.agent.environment.time_speed)
                        await asyncio.sleep(base_sleep / sim_speed)
                        return
                    
                    # Calculate elapsed simulation time
                    time_diff = (current_sim_time - self.last_spawn_time).total_seconds()
                    
                    # Check current car count and target
                    current_cars = len(self.agent.environment.cars)
                    min_cars = 10
                    max_cars = 50
                    target_cars = int(min_cars + (self.agent.environment.current_traffic_density * (max_cars - min_cars)))
                    
                    # Process spawn checks based on elapsed simulation time
                    # This ensures spawn rate scales proportionally with simulation speed
                    if time_diff >= self.spawn_interval_sim:
                        # Calculate how many spawn intervals have passed
                        spawn_intervals_passed = time_diff / self.spawn_interval_sim
                        
                        # If below target, spawn more aggressively
                        if current_cars < target_cars:
                            # Spawn one car per interval that passed (or more if very below target)
                            spawns_needed = max(1, int(spawn_intervals_passed))
                            # If significantly below target, spawn even more
                            if current_cars < target_cars * 0.7:
                                spawns_needed = int(spawn_intervals_passed * 1.5)
                            spawns_needed = min(spawns_needed, 20)  # Cap at 20 per check
                        else:
                            # At or above target - use probability, but still process all intervals
                            spawns_needed = max(1, int(spawn_intervals_passed))
                            spawns_needed = min(spawns_needed, 10)  # Cap at 10 per check
                        
                        # Process spawns
                        spawned_count = 0
                        for _ in range(spawns_needed):
                            # Check if we should spawn a new car based on traffic density
                            if self.agent.environment.should_spawn_car():
                                car_id = self.agent.next_car_id
                                self.agent.next_car_id += 1

                                try:
                                    new_car = CarAgent(f"carro_{car_id}@localhost", "pass", self.agent.environment)
                                    await new_car.start(auto_register=True)
                                    spawned_count += 1
                                    # print(f"[MAP UPDATER] Novo carro spawned: carro_{car_id}")
                                except Exception as e:
                                    print(f"[MAP UPDATER] Erro ao criar carro: {e}")  # Keep errors
                        
                        # Update last spawn time to current time
                        # This ensures we process all elapsed time, not just one interval
                        self.last_spawn_time = current_sim_time
                    
                    # Sleep time: must be inversely proportional to simulation speed
                    # If sim is 10x faster, we need to check 10x more frequently in real time
                    # to catch all the simulation time that passes
                    base_sleep = 0.05  # Base check frequency (20 checks per second real time)
                    sim_speed = max(1, self.agent.environment.time_speed)
                    adjusted_sleep = base_sleep / sim_speed
                    
                    # Additional reduction when significantly below target
                    if current_cars < target_cars * 0.8:
                        adjusted_sleep *= 0.5
                    
                    # Minimum sleep to avoid overwhelming the system
                    adjusted_sleep = max(0.002, adjusted_sleep)  # Very short minimum
                    await asyncio.sleep(adjusted_sleep)

            self.add_behaviour(CarSpawnBehaviour(self))
        #else:
            # print("[MAP UPDATER] DEBUG MODE: Periodic car spawning disabled")

        # Comportamento periódico para criar um veículo de emergência
        # Uses simulation time, not real time, so it scales with time speed
        class EmergencySpawnBehaviour(CyclicBehaviour):
            def __init__(self, agent):
                super().__init__()
                self.agent = agent
                self.last_spawn_time = None  # Store last spawn time in simulation time
                self.spawn_interval_sim = 15.0  # Spawn interval in simulation seconds
            
            async def run(self):
                # Use simulation time, not real time
                current_sim_time = self.agent.environment.simulation_time
                
                # Initialize last_spawn_time on first run
                if self.last_spawn_time is None:
                    self.last_spawn_time = current_sim_time
                    # Adjust sleep based on simulation speed
                    base_sleep = 0.1
                    sim_speed = max(1, self.agent.environment.time_speed)
                    await asyncio.sleep(base_sleep / sim_speed)
                    return
                
                # Calculate elapsed simulation time
                time_diff = (current_sim_time - self.last_spawn_time).total_seconds()
                
                # Check if enough simulation time has passed
                if time_diff >= self.spawn_interval_sim:
                    emergency_id = self.agent.next_emergency_id
                    self.agent.next_emergency_id += 1
                    
                    # print(f"[MAP UPDATER {self.agent.jid}] Criando veículo de emergência #{emergency_id}")
                    try:
                        emergency_car = EmergencyCarAgent(f"emergencia_carro_{emergency_id}@localhost", "pass", self.agent.environment)
                        await emergency_car.start(auto_register=True)
                    except Exception as e:
                        print(f"[MAP UPDATER] Erro ao criar veículo emergência: {e}")
                    
                    # Update last spawn time
                    self.last_spawn_time = current_sim_time
                
                # Small sleep to avoid busy waiting - adjust based on simulation speed
                base_sleep = 0.1
                sim_speed = max(1, self.agent.environment.time_speed)
                adjusted_sleep = base_sleep / sim_speed
                adjusted_sleep = max(0.005, adjusted_sleep)  # Minimum sleep
                await asyncio.sleep(adjusted_sleep)

        self.add_behaviour(EmergencySpawnBehaviour(self))

        # Comportamento periódico (15s) para análise de congestionamento e ajuste de semáforos
        class CongestionAnalysisBehaviour(PeriodicBehaviour):
            async def run(self):
                # print(f"[MAP UPDATER {self.agent.jid}] Analisando padrões de tráfego e ajustando semáforos...")

                # Mapeia cruzamento para agente de semáforo
                crossing_to_agent = {
                    "top_left": "semaforos_4@localhost",
                    "top_mid": "semaforos_5@localhost",
                    "top_right": "semaforos_6@localhost",
                    "bottom_left": "semaforos_1@localhost",
                    "bottom_mid": "semaforos_2@localhost",
                    "bottom_right": "semaforos_3@localhost"
                }

                # Analisa cada cruzamento e ajusta semáforos
                for crossing, tl_jid in crossing_to_agent.items():
                    # Analisa padrões de tráfego para este cruzamento
                    traffic_analysis = await self.analyze_intersection_traffic(crossing)
                    
                    if traffic_analysis:
                        # Calcula ajuste de tempo baseado na análise
                        timing_adjustment = self.calculate_timing_adjustment(traffic_analysis)
                        
                        if timing_adjustment:
                            # Envia ajuste para o semáforo
                            await self.request_traffic_adjustment(
                                crossing, 
                                tl_jid, 
                                timing_adjustment
                            )

            async def analyze_intersection_traffic(self, intersection_id):
                """
                Analisa padrões de tráfego em um cruzamento.
                Retorna análise com carros parados por direção (vertical/horizontal).
                """
                # Conta carros parados por direção
                vertical_stopped = 0  # top/bottom (norte/sul)
                horizontal_stopped = 0  # left/right (este/oeste)
                
                # Padrões de IDs de semáforos para cada direção
                # IDs são formatados como: {intersection_id}_{dir[0]}_{pos[0]}
                # dir[0] pode ser: 't' (top), 'b' (bottom), 'l' (left), 'r' (right)
                # vertical = top/bottom (t/b), horizontal = left/right (l/r)
                vertical_patterns = ['_t_', '_b_']  # top e bottom
                horizontal_patterns = ['_l_', '_r_']  # left e right
                
                # Conta carros parados em cada direção
                cars_stopped = self.agent.environment.cars_stopped_at_tl
                for tl_id, cars in cars_stopped.items():
                    # Verifica se este semáforo pertence a este cruzamento
                    tl_id_str = str(tl_id).lower()
                    if intersection_id in tl_id_str:
                        # Conta apenas carros que realmente existem
                        valid_cars = [c for c in cars if c in self.agent.environment.car_positions]
                        car_count = len(valid_cars)
                        
                        # Determina direção baseado no ID do semáforo
                        # Procura por padrões como _t_ ou _b_ (vertical) ou _l_ ou _r_ (horizontal)
                        if any(pattern in tl_id_str for pattern in vertical_patterns):
                            vertical_stopped += car_count
                        elif any(pattern in tl_id_str for pattern in horizontal_patterns):
                            horizontal_stopped += car_count
                
                total_stopped = vertical_stopped + horizontal_stopped
                
                # Retorna análise se houver carros parados
                if total_stopped > 0:
                    return {
                        'intersection_id': intersection_id,
                        'vertical_stopped': vertical_stopped,
                        'horizontal_stopped': horizontal_stopped,
                        'total_stopped': total_stopped,
                        'vertical_ratio': vertical_stopped / total_stopped if total_stopped > 0 else 0.5,
                        'horizontal_ratio': horizontal_stopped / total_stopped if total_stopped > 0 else 0.5
                    }
                
                return None

            def calculate_timing_adjustment(self, traffic_analysis):
                """
                Calcula ajuste de tempo baseado na análise de tráfego.
                Retorna informação sobre qual direção precisa reduzir tempo vermelho.
                """
                vertical_stopped = traffic_analysis['vertical_stopped']
                horizontal_stopped = traffic_analysis['horizontal_stopped']
                total_stopped = traffic_analysis['total_stopped']
                
                # Se não há muitos carros parados, não ajusta
                if total_stopped < 2:
                    return None
                
                # Determina qual direção tem mais carros parados (precisa reduzir tempo vermelho)
                # Reduz tempo vermelho da direção com mais carros parados
                if vertical_stopped > horizontal_stopped and vertical_stopped >= 2:
                    # Mais carros parados na direção vertical -> reduz tempo vermelho vertical
                    red_reduction = min(3, int(vertical_stopped * 0.4))  # Reduz 1-3 segundos
                    return {
                        'direction': 'vertical',  # vertical = top/bottom (todas as 3 faixas)
                        'red_reduction_seconds': red_reduction,
                        'duration_seconds': 45  # Ajuste válido por 45 segundos de simulação
                    }
                elif horizontal_stopped > vertical_stopped and horizontal_stopped >= 2:
                    # Mais carros parados na direção horizontal -> reduz tempo vermelho horizontal
                    red_reduction = min(3, int(horizontal_stopped * 0.4))  # Reduz 1-3 segundos
                    return {
                        'direction': 'horizontal',  # horizontal = left/right (todas as 3 faixas)
                        'red_reduction_seconds': red_reduction,
                        'duration_seconds': 45
                    }
                
                return None

            async def request_traffic_adjustment(self, crossing, tl_jid, timing_adjustment):
                """Informa aos semáforos para reduzir tempo vermelho (FIPA Inform Protocol)"""
                conv_id = str(uuid.uuid4())

                # Cria mensagem informando redução de tempo vermelho
                adjustment_info = {
                    'action': 'reduce_red_time',
                    'direction': timing_adjustment['direction'],  # 'vertical' ou 'horizontal'
                    'red_reduction_seconds': timing_adjustment['red_reduction_seconds'],
                    'duration': timing_adjustment['duration_seconds'],
                    'intersection': crossing,
                    'apply_to_all_lanes': True  # Aplica a todas as 3 faixas da direção
                }
                
                import json
                msg = Message(to=tl_jid)
                msg.set_metadata("performative", "inform")  # Inform, não Request
                msg.set_metadata("protocol", "fipa-inform")
                msg.set_metadata("conversation-id", conv_id)
                msg.set_metadata("action", "reduce_red_time")
                msg.body = json.dumps(adjustment_info)

                await self.send(msg)
                # print(f"[MAP UPDATER {self.agent.jid}] Informação enviada para {tl_jid}: "
                #       f"Reduzir tempo vermelho {timing_adjustment['direction']} em "
                #       f"{timing_adjustment['red_reduction_seconds']}s (todas as 3 faixas)")

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

        congestion_interval = 5  # Analisa e ajusta a cada 5 segundos
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

                    # if performative == "agree":
                    #     print(f"[MAP UPDATER {self.agent.jid}] AGREE recebido de {msg.sender}")
                    #     print(f"[MAP UPDATER {self.agent.jid}] Semáforo aceitou ajustar tempos")
                    #
                    # elif performative == "inform":
                    #     print(f"[MAP UPDATER {self.agent.jid}] INFORM recebido de {msg.sender}")
                    #     print(f"[MAP UPDATER {self.agent.jid}] Resultado: {msg.body}")
                    #
                    # elif performative == "refuse":
                    #     print(f"[MAP UPDATER {self.agent.jid}] REFUSE recebido de {msg.sender}")
                    #     print(f"[MAP UPDATER {self.agent.jid}] Motivo: {msg.body}")
                    #
                    # elif performative == "failure":
                    #     print(f"[MAP UPDATER {self.agent.jid}] FAILURE recebido de {msg.sender}")
                    #     print(f"[MAP UPDATER {self.agent.jid}] Erro: {msg.body}")

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

                # print(f"[MAP UPDATER {self.agent.jid}] Broadcasting: {alert_msg}")

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
