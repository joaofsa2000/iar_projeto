#MapUpdaterAgent.py

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
        #Comportamento periódico para atualizar o mapa pygame
        class PeriodicBehav(PeriodicBehaviour):
            async def run(self):
                self.agent.environment.update_map()

            async def on_end(self):
                await self.agent.stop()

        start_at = datetime.now() + timedelta(seconds=2)
        period = PeriodicBehav(period=0, start_at=start_at)
        self.add_behaviour(period)

        #Comportamento periodico (10sec) para gerar um veiculo de emergencia no mapa
        #Criando um novo agente do tipo EmergencyCarAgent
        class EmergencyBehav(PeriodicBehaviour):
            async def run(self):
                print("EMERGENCY")
                emergency_car = EmergencyCarAgent("em_car_1@localhost", "pass", self.agent.environment)
                await emergency_car.start(auto_register=True) 

            async def on_end(self):
                await self.agent.stop()

        time_span = 10
        start_at = datetime.now() + timedelta(seconds=time_span)
        period = EmergencyBehav(period=time_span, start_at=start_at)
        self.add_behaviour(period)

        #Comportamento periódico (25sec) para validar o modelo machine learnig para a previsão de acidentes
        class CrashBehav(PeriodicBehaviour):
            async def run(self):
                CROSSES = {
                    "top_left": 0,
                    "top_mid": 0,
                    "top_right": 0,
                    "bottom_left": 0,
                    "bottom_mid": 0,
                    "bottom_right": 0
                }

                #Identifica o cruzamento com maior número de carros
                cars_stopped = self.agent.environment.cars_stopped_at_tl
                for x in cars_stopped:
                    cross = x[0:len(x) - 4]
                    CROSSES[cross] += len(self.agent.environment.cars_stopped_at_tl[x])

                max_cross = max(CROSSES, key=lambda k: CROSSES[k])
                vehicle_count = max(CROSSES.values())
                
                #Envia os parametros de número de carros, hora do dia e dia da semana e o modelo retorna se existe acidente ou não
                if await self.predict_with_svm_model(vehicle_count):
                    print("CRASH")
                    self.agent.environment.activate_map_crash(max_cross)

                    # Dá uma duração para o acidente entre 0,5 e 2 minutos
                    duration = round(random.uniform(0.5 * 60, 2 * 60))
                    print("CRASH DURATION: ", duration)
                    await asyncio.sleep(duration)

                    print("CRASH OVER")
                    self.agent.environment.deactivate_map_crash()

            #Comportamento periódico (25sec) que usa o algoritmo SVM para fazer uma previsão de acidente de acordo com os parametros:
            # - Número de veiculos
            # - Hora do dia
            # - Dia da semana
            async def predict_with_svm_model(self, veiculos):
                # Carregar o modelo SVM pré-treinado
                loaded_model = joblib.load('MachineLearning/svm_model.pkl')

                current_time_of_day_index = self.agent.environment.TIMES_OF_DAY.index(self.agent.environment.time_of_day)
                current_day_of_week_index = self.agent.environment.DAYS_OF_WEEK.index(self.agent.environment.day_of_week) + 1

                # Converter os valores de entrada para tipos numéricos
                dia = int(current_day_of_week_index)
                hora = int(current_time_of_day_index)
                veiculos = int(veiculos)

                # Esta aqui um pequeno erro tenho de alterar o codigo de treino do modelo
                new_data = pd.DataFrame([[dia, hora, veiculos]])

                # Preve com os dados inseridos
                predictions = loaded_model.predict(new_data)

                #print(predictions)
                return predictions[0]

            async def on_end(self):
                await self.agent.stop()

        time_span = 25
        start_at = datetime.now() + timedelta(seconds=time_span)
        period = CrashBehav(period=time_span, start_at=start_at)
        self.add_behaviour(period)

        #Comportamento periódico (30sec) responsável por atualizar a hora do dia/dia da semana no mapa
        class ClockBehav(PeriodicBehaviour):
            async def run(self):
                index_day_of_week_max = len(self.agent.environment.DAYS_OF_WEEK) - 1
                index_time_of_day_max = len(self.agent.environment.TIMES_OF_DAY) - 1

                current_time_of_day_index = self.agent.environment.TIMES_OF_DAY.index(self.agent.environment.time_of_day)
                current_day_of_week_index = self.agent.environment.DAYS_OF_WEEK.index(self.agent.environment.day_of_week)
                if current_time_of_day_index == index_time_of_day_max:
                    self.agent.environment.time_of_day = self.agent.environment.TIMES_OF_DAY[0]

                    if current_day_of_week_index == index_day_of_week_max:
                        self.agent.environment.day_of_week = self.agent.environment.DAYS_OF_WEEK[0]
                    else:
                        self.agent.environment.day_of_week = self.agent.environment.DAYS_OF_WEEK[current_day_of_week_index + 1]

                else:
                    self.agent.environment.time_of_day = self.agent.environment.TIMES_OF_DAY[current_time_of_day_index + 1]

            async def on_end(self):
                await self.agent.stop()

        time_span = 30
        start_at = datetime.now() + timedelta(seconds=time_span)
        period = ClockBehav(period=time_span, start_at=start_at)
        self.add_behaviour(period)
