import asyncio

import pygame
import spade
from Agents.CarAgent import CarAgent
from Agents.MapUpdaterAgent import MapUpdaterAgent
from Agents.TrafficLightAgent import TrafficLightAgent

from Environment.environment import Environment
from Models.LightStatus import LightStatus
from Models.TrafficLightModel import CrossingTrafficLightModel, SideTrafficLightModel, TrafficLightModel

async def main():
    # Cria o ambiente
    environment = Environment()

    # Cria e inicia o agente central
    map_updater = MapUpdaterAgent("map_updater@localhost", "pass", environment)
    await map_updater.start(auto_register=True)

    # Definição dos semáforos
    tl_1_disposition = CrossingTrafficLightModel(
        "bottom_left",
        SideTrafficLightModel(
            TrafficLightModel((278, 621), 0, LightStatus.RED),
            TrafficLightModel((300, 621), 0, LightStatus.RED),
            TrafficLightModel((322, 621), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((256, 442), 180, LightStatus.RED),
            TrafficLightModel((234, 442), 180, LightStatus.RED),
            TrafficLightModel((212, 442), 180, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((178, 542), -90, LightStatus.RED),
            TrafficLightModel((178, 564), -90, LightStatus.RED),
            TrafficLightModel((178, 586), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((357, 519), 90, LightStatus.RED),
            TrafficLightModel((357, 497), 90, LightStatus.RED),
            TrafficLightModel((357, 475), 90, LightStatus.RED),
        )
    )

    tl_2_disposition = CrossingTrafficLightModel(
        "bottom_mid",
        SideTrafficLightModel(
            TrafficLightModel((637, 621), 0, LightStatus.RED),
            TrafficLightModel((659, 621), 0, LightStatus.RED),
            TrafficLightModel((681, 621), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((616, 442), 180, LightStatus.RED),
            TrafficLightModel((594, 442), 180, LightStatus.RED),
            TrafficLightModel((572, 442), 180, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((537, 541), -90, LightStatus.RED),
            TrafficLightModel((537, 563), -90, LightStatus.RED),
            TrafficLightModel((537, 586), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((717, 519), 90, LightStatus.RED),
            TrafficLightModel((717, 497), 90, LightStatus.RED),
            TrafficLightModel((717, 474), 90, LightStatus.RED),
        )
    )

    tl_3_disposition = CrossingTrafficLightModel(
        "bottom_right",
        SideTrafficLightModel(
            TrafficLightModel((1002, 621), 0, LightStatus.RED),
            TrafficLightModel((1024, 621), 0, LightStatus.RED),
            TrafficLightModel((1046, 621), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((981, 442), 180, LightStatus.RED),
            TrafficLightModel((959, 442), 180, LightStatus.RED),
            TrafficLightModel((937, 442), 180, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((902, 541), -90, LightStatus.RED),
            TrafficLightModel((902, 563), -90, LightStatus.RED),
            TrafficLightModel((902, 585), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((1082, 519), 90, LightStatus.RED),
            TrafficLightModel((1082, 497), 90, LightStatus.RED),
            TrafficLightModel((1082, 475), 90, LightStatus.RED),
        )
    )

    tl_4_disposition = CrossingTrafficLightModel(
        "top_left",
        SideTrafficLightModel(
            TrafficLightModel((278, 271), 0, LightStatus.RED),
            TrafficLightModel((300, 271), 0, LightStatus.RED),
            TrafficLightModel((322, 271), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((256, 92), 180, LightStatus.RED),
            TrafficLightModel((234, 92), 180, LightStatus.RED),
            TrafficLightModel((212, 92), 180, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((178, 191), -90, LightStatus.RED),
            TrafficLightModel((178, 213), -90, LightStatus.RED),
            TrafficLightModel((178, 235), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((358, 169), 90, LightStatus.RED),
            TrafficLightModel((358, 147), 90, LightStatus.RED),
            TrafficLightModel((358, 125), 90, LightStatus.RED),
        )
    )

    tl_5_disposition = CrossingTrafficLightModel(
        "top_mid",
        SideTrafficLightModel(
            TrafficLightModel((637, 271), 0, LightStatus.RED),
            TrafficLightModel((659, 271), 0, LightStatus.RED),
            TrafficLightModel((681, 271), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((615, 92), 180, LightStatus.RED),
            TrafficLightModel((593, 92), 180, LightStatus.RED),
            TrafficLightModel((571, 92), 180, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((537, 191), -90, LightStatus.RED),
            TrafficLightModel((537, 213), -90, LightStatus.RED),
            TrafficLightModel((537, 235), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((717, 169), 90, LightStatus.RED),
            TrafficLightModel((717, 147), 90, LightStatus.RED),
            TrafficLightModel((717, 125), 90, LightStatus.RED),
        )
    )

    tl_6_disposition = CrossingTrafficLightModel(
        "top_right",
        SideTrafficLightModel(
            TrafficLightModel((1002, 271), 0, LightStatus.RED),
            TrafficLightModel((1024, 271), 0, LightStatus.RED),
            TrafficLightModel((1046, 271), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((980, 92), 180, LightStatus.RED),
            TrafficLightModel((958, 92), 180, LightStatus.RED),
            TrafficLightModel((936, 92), 180, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((902, 191), -90, LightStatus.RED),
            TrafficLightModel((902, 213), -90, LightStatus.RED),
            TrafficLightModel((902, 235), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((1082, 169), 90, LightStatus.RED),
            TrafficLightModel((1082, 147), 90, LightStatus.RED),
            TrafficLightModel((1082, 125), 90, LightStatus.RED),
        )
    )

    # Cria e inicia agentes semáforos
    tl_agents = [
        TrafficLightAgent("tl_1@localhost", "pass", tl_1_disposition, environment),
        TrafficLightAgent("tl_2@localhost", "pass", tl_2_disposition, environment),
        TrafficLightAgent("tl_3@localhost", "pass", tl_3_disposition, environment),
        TrafficLightAgent("tl_4@localhost", "pass", tl_4_disposition, environment),
        TrafficLightAgent("tl_5@localhost", "pass", tl_5_disposition, environment),
        TrafficLightAgent("tl_6@localhost", "pass", tl_6_disposition, environment),
    ]

    for tl in tl_agents:
        await tl.start(auto_register=True)

    # Cria e inicia todos os agentes carros
    for x in range(30):
        car = CarAgent(f"car_{x}@localhost", "pass", environment)
        await car.start(auto_register=True)
    try:
        while True:
            environment.update_map()  # desenha e processa eventos
            await asyncio.sleep(0)   # dá chance para os agentes rodarem
    except KeyboardInterrupt:
        print("A encerrar a simulação...")
        pygame.quit()

if __name__ == "__main__":
    spade.run(main())