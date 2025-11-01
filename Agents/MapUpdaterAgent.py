import asyncio
from datetime import datetime, timedelta
import random
import time
import uuid
import joblib
import pandas as pd

from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour, CyclicBehaviour
from spade.message import Message
from spade.template import Template

from Agents.EmergencyCarAgent import EmergencyCarAgent


class MapUpdaterAgent(Agent):
    def __init__(self, jid, password, environment):
        super().__init__(jid, password)
        self.environment = environment
        self.id = jid

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

        # Comportamento periódico (10s) para criar um veículo de emergência
        class EmergencySpawnBehaviour(PeriodicBehaviour):
            async def run(self):
                print(f"[MAP UPDATER {self.agent.jid}] Criando veículo de emergência")
                emergency_car = EmergencyCarAgent("emergencia_carro_1@localhost", "pass", self.agent.environment)
                await emergency_car.start(auto_register=True)

            async def on_end(self):
                await self.agent.stop()

        emergency_interval = 10
        start_at = datetime.now() + timedelta(seconds=emergency_interval)
        period = EmergencySpawnBehaviour(period=emergency_interval, start_at=start_at)
        self.add_behaviour(period)

        # Comportamento periódico (25s) para previsão de acidentes via Machine Learning
        class CrashPredictionBehaviour(PeriodicBehaviour):
            async def run(self):
                print(f"[MAP UPDATER {self.agent.jid}] Analisando risco de acidentes...")

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
                    CROSSES[cross] += len(self.agent.environment.cars_stopped_at_tl[x])

                max_cross = max(CROSSES, key=lambda k: CROSSES[k])
                vehicle_count = max(CROSSES.values())

                print(
                    f"[MAP UPDATER {self.agent.jid}] Cruzamento mais congestionado: {max_cross} ({vehicle_count} veículos)")

                # Simular previsão de acidente (pode ser substituído por modelo ML real)
                crash_risk = vehicle_count > 5  # Exemplo simples

                if crash_risk:
                    print(f"[MAP UPDATER {self.agent.jid}] RISCO DE ACIDENTE ALTO em {max_cross}!")
                    # FIPA REQUEST PROTOCOL - Solicitar aos semáforos para ajustar tempos
                    await self.request_traffic_adjustment(max_cross, vehicle_count)

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

            async def on_end(self):
                await self.agent.stop()

        crash_interval = 25
        start_at = datetime.now() + timedelta(seconds=crash_interval)
        period = CrashPredictionBehaviour(period=crash_interval, start_at=start_at)
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
        # FIPA INFORM PROTOCOL - Broadcast de Alertas
        # ============================================================
        class BroadcastAlertBehaviour(PeriodicBehaviour):
            """Envia alertas periódicos sobre o estado do sistema"""

            async def run(self):
                # Coleta estatísticas do sistema
                total_cars = len(self.agent.environment.car_positions)
                total_stopped = sum(len(cars) for cars in self.agent.environment.cars_stopped_at_tl.values())

                # Broadcast INFORM para todos os agentes (exemplo)
                alert_msg = f"SYSTEM_STATUS: {total_cars} vehicles, {total_stopped} stopped at lights"

                print(f"[MAP UPDATER {self.agent.jid}] {alert_msg}")

                # Pode enviar para agentes específicos se necessário
                # await self.broadcast_to_all_agents(alert_msg)

        # Descomente para ativar broadcast periódico
        # broadcast_interval = 30
        # start_at = datetime.now() + timedelta(seconds=broadcast_interval)
        # self.add_behaviour(BroadcastAlertBehaviour(period=broadcast_interval, start_at=start_at))