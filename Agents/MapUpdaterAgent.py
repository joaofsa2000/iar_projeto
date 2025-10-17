import asyncio
from datetime import datetime, timedelta
import random
import time
import joblib
import pandas as pd

from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour

from Agents.EmergencyCarAgent import EmergencyCarAgent


class MapUpdaterAgent(Agent):
    def __init__(self, jid, password, environment):
        super().__init__(jid, password)
        self.environment = environment
        self.id = jid

    async def setup(self):
        # Comportamento periódico para atualizar o mapa pygame
        class PeriodicBehav(PeriodicBehaviour):
            async def run(self):
                self.agent.environment.update_map()

            async def on_end(self):
                await self.agent.stop()

        start_at = datetime.now() + timedelta(seconds=2)
        period = PeriodicBehav(period=0, start_at=start_at)
        self.add_behaviour(period)

        # Comportamento periódico (10s) para criar um veículo de emergência
        class EmergencyBehav(PeriodicBehaviour):
            async def run(self):
                print("EMERGENCY")
                emergency_car = EmergencyCarAgent("emergencia_carro_1@localhost", "pass", self.agent.environment)
                await emergency_car.start(auto_register=True)

            async def on_end(self):
                await self.agent.stop()

        emergency_interval = 10
        start_at = datetime.now() + timedelta(seconds=emergency_interval)
        period = EmergencyBehav(period=emergency_interval, start_at=start_at)
        self.add_behaviour(period)

        # Comportamento periódico (25s) para previsão de acidentes via SVM
        class CrashBehav(PeriodicBehaviour):
            async def run(self):
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

                # usar machine learning

            async def on_end(self):
                await self.agent.stop()

        crash_interval = 25
        start_at = datetime.now() + timedelta(seconds=crash_interval)
        period = CrashBehav(period=crash_interval, start_at=start_at)
        self.add_behaviour(period)

