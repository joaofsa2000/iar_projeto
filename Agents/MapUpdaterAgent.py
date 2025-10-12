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
                emergency_car = EmergencyCarAgent("em_car_1@localhost", "pass", self.agent.environment)
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

                # Faz a previsão de acidente usando modelo SVM
                if await self.predict_with_svm_model(vehicle_count):
                    print("CRASH")
                    self.agent.environment.activate_map_crash(max_cross)

                    # Duração do acidente entre 0.5 e 2 minutos
                    duration = round(random.uniform(0.5 * 60, 2 * 60))
                    print("CRASH DURATION:", duration)
                    await asyncio.sleep(duration)

                    print("CRASH OVER")
                    self.agent.environment.deactivate_map_crash()

            # Usa modelo SVM pré-treinado para prever acidentes
            async def predict_with_svm_model(self, vehicle_count):
                loaded_model = joblib.load('MachineLearning/svm_model.pkl')

                current_time_index = self.agent.environment.TIMES_OF_DAY.index(self.agent.environment.time_of_day)
                current_day_index = self.agent.environment.DAYS_OF_WEEK.index(self.agent.environment.day_of_week) + 1

                # Cria DataFrame com os dados de entrada
                new_data = pd.DataFrame([[int(current_day_index), int(current_time_index), int(vehicle_count)]])

                # Previsão de acidente (0 = sem acidente, 1 = acidente)
                predictions = loaded_model.predict(new_data)
                return predictions[0]

            async def on_end(self):
                await self.agent.stop()

        crash_interval = 25
        start_at = datetime.now() + timedelta(seconds=crash_interval)
        period = CrashBehav(period=crash_interval, start_at=start_at)
        self.add_behaviour(period)

        # Comportamento periódico (30s) para atualizar hora do dia e dia da semana
        class ClockBehav(PeriodicBehaviour):
            async def run(self):
                days_max_index = len(self.agent.environment.DAYS_OF_WEEK) - 1
                times_max_index = len(self.agent.environment.TIMES_OF_DAY) - 1

                current_time_index = self.agent.environment.TIMES_OF_DAY.index(self.agent.environment.time_of_day)
                current_day_index = self.agent.environment.DAYS_OF_WEEK.index(self.agent.environment.day_of_week)

                # Atualiza hora do dia e dia da semana
                if current_time_index == times_max_index:
                    self.agent.environment.time_of_day = self.agent.environment.TIMES_OF_DAY[0]
                    if current_day_index == days_max_index:
                        self.agent.environment.day_of_week = self.agent.environment.DAYS_OF_WEEK[0]
                    else:
                        self.agent.environment.day_of_week = self.agent.environment.DAYS_OF_WEEK[current_day_index + 1]
                else:
                    self.agent.environment.time_of_day = self.agent.environment.TIMES_OF_DAY[current_time_index + 1]

            async def on_end(self):
                await self.agent.stop()

        clock_interval = 30
        start_at = datetime.now() + timedelta(seconds=clock_interval)
        period = ClockBehav(period=clock_interval, start_at=start_at)
        self.add_behaviour(period)
