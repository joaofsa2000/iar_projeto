import asyncio
import pygame
import spade

# Importar os novos agentes com protocolos FIPA
from Agents.CarAgent import CarAgent
from Agents.MapUpdaterAgent import MapUpdaterAgent
from Agents.TrafficLightAgent import TrafficLightAgent
from Agents.EmergencyCarAgent import EmergencyCarAgent

from Environment.environment import Environment
from Models.LightStatus import LightStatus
from Models.TrafficLightModel import CrossingTrafficLightModel, SideTrafficLightModel, TrafficLightModel


async def main():
    print("=" * 80)
    print("SISTEMA DE GESTÃO DE TRÁFEGO COM PROTOCOLOS FIPA")
    print("=" * 80)
    print("\nProtocolos implementados:")
    print("  1. FIPA Request Protocol - Veículos de emergência ↔ Semáforos")
    print("  2. FIPA Subscribe Protocol - Carros normais ↔ Semáforos")
    print("  3. FIPA Request Protocol - MapUpdater ↔ Semáforos (ajuste de tempos)")
    print("=" * 80 + "\n")

    # Cria o ambiente
    environment = Environment()

    # Cria e inicia o agente central (MapUpdater)
    print("[SETUP] Iniciando agente central (MapUpdater)...")
    map_updater = MapUpdaterAgent("central@localhost", "pass", environment)
    await map_updater.start(auto_register=True)

    # Definição dos semáforos
    print("[SETUP] Configurando semáforos...")

    tl_1_disposition = CrossingTrafficLightModel(
        "bottom_left",
        SideTrafficLightModel(
            TrafficLightModel((178, 542), -90, LightStatus.RED),
            TrafficLightModel((178, 564), -90, LightStatus.RED),
            TrafficLightModel((178, 586), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((278, 621), 0, LightStatus.RED),
            TrafficLightModel((300, 621), 0, LightStatus.RED),
            TrafficLightModel((322, 621), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((357, 519), 90, LightStatus.RED),
            TrafficLightModel((357, 497), 90, LightStatus.RED),
            TrafficLightModel((357, 475), 90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((256, 442), 180, LightStatus.RED),
            TrafficLightModel((234, 442), 180, LightStatus.RED),
            TrafficLightModel((212, 442), 180, LightStatus.RED),
        )
    )

    tl_2_disposition = CrossingTrafficLightModel(
        "bottom_mid",
        SideTrafficLightModel(
            TrafficLightModel((537, 541), -90, LightStatus.RED),
            TrafficLightModel((537, 563), -90, LightStatus.RED),
            TrafficLightModel((537, 586), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((637, 621), 0, LightStatus.RED),
            TrafficLightModel((659, 621), 0, LightStatus.RED),
            TrafficLightModel((681, 621), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((717, 519), 90, LightStatus.RED),
            TrafficLightModel((717, 497), 90, LightStatus.RED),
            TrafficLightModel((717, 474), 90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((616, 442), 180, LightStatus.RED),
            TrafficLightModel((594, 442), 180, LightStatus.RED),
            TrafficLightModel((572, 442), 180, LightStatus.RED),
        )
    )

    tl_3_disposition = CrossingTrafficLightModel(
        "bottom_right",
        SideTrafficLightModel(
            TrafficLightModel((902, 541), -90, LightStatus.RED),
            TrafficLightModel((902, 563), -90, LightStatus.RED),
            TrafficLightModel((902, 585), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((1002, 621), 0, LightStatus.RED),
            TrafficLightModel((1024, 621), 0, LightStatus.RED),
            TrafficLightModel((1046, 621), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((1082, 519), 90, LightStatus.RED),
            TrafficLightModel((1082, 497), 90, LightStatus.RED),
            TrafficLightModel((1082, 475), 90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((981, 442), 180, LightStatus.RED),
            TrafficLightModel((959, 442), 180, LightStatus.RED),
            TrafficLightModel((937, 442), 180, LightStatus.RED),
        )
    )

    tl_4_disposition = CrossingTrafficLightModel(
        "top_left",
        SideTrafficLightModel(
            TrafficLightModel((178, 191), -90, LightStatus.RED),
            TrafficLightModel((178, 213), -90, LightStatus.RED),
            TrafficLightModel((178, 235), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((278, 271), 0, LightStatus.RED),
            TrafficLightModel((300, 271), 0, LightStatus.RED),
            TrafficLightModel((322, 271), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((358, 169), 90, LightStatus.RED),
            TrafficLightModel((358, 147), 90, LightStatus.RED),
            TrafficLightModel((358, 125), 90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((256, 92), 180, LightStatus.RED),
            TrafficLightModel((234, 92), 180, LightStatus.RED),
            TrafficLightModel((212, 92), 180, LightStatus.RED),
        ),
    )

    tl_5_disposition = CrossingTrafficLightModel(
        "top_mid",
        SideTrafficLightModel(
            TrafficLightModel((537, 191), -90, LightStatus.RED),
            TrafficLightModel((537, 213), -90, LightStatus.RED),
            TrafficLightModel((537, 235), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((637, 271), 0, LightStatus.RED),
            TrafficLightModel((659, 271), 0, LightStatus.RED),
            TrafficLightModel((681, 271), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((717, 169), 90, LightStatus.RED),
            TrafficLightModel((717, 147), 90, LightStatus.RED),
            TrafficLightModel((717, 125), 90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((615, 92), 180, LightStatus.RED),
            TrafficLightModel((593, 92), 180, LightStatus.RED),
            TrafficLightModel((571, 92), 180, LightStatus.RED),
        ),
    )

    tl_6_disposition = CrossingTrafficLightModel(
        "top_right",
        SideTrafficLightModel(
            TrafficLightModel((902, 191), -90, LightStatus.RED),
            TrafficLightModel((902, 213), -90, LightStatus.RED),
            TrafficLightModel((902, 235), -90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((1002, 271), 0, LightStatus.RED),
            TrafficLightModel((1024, 271), 0, LightStatus.RED),
            TrafficLightModel((1046, 271), 0, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((1082, 169), 90, LightStatus.RED),
            TrafficLightModel((1082, 147), 90, LightStatus.RED),
            TrafficLightModel((1082, 125), 90, LightStatus.RED),
        ),
        SideTrafficLightModel(
            TrafficLightModel((980, 92), 180, LightStatus.RED),
            TrafficLightModel((958, 92), 180, LightStatus.RED),
            TrafficLightModel((936, 92), 180, LightStatus.RED),
        )
    )

    # Cria e inicia agentes semáforos com offsets diferentes
    print("[SETUP] Iniciando agentes de semáforos com FIPA Request e Subscribe Protocols...")
    tl_agents = [
        TrafficLightAgent("semaforos_1@localhost", "pass", tl_1_disposition, environment, offset_seconds=0),
        TrafficLightAgent("semaforos_2@localhost", "pass", tl_2_disposition, environment, offset_seconds=2),
        TrafficLightAgent("semaforos_3@localhost", "pass", tl_3_disposition, environment, offset_seconds=4),
        TrafficLightAgent("semaforos_4@localhost", "pass", tl_4_disposition, environment, offset_seconds=5),
        TrafficLightAgent("semaforos_5@localhost", "pass", tl_5_disposition, environment, offset_seconds=7),
        TrafficLightAgent("semaforos_6@localhost", "pass", tl_6_disposition, environment, offset_seconds=9),
    ]

    for tl in tl_agents:
        await tl.start(auto_register=True)

    # Cria e inicia agentes carros (com FIPA Subscribe Protocol)
    print("[SETUP] Iniciando agentes de carros com FIPA Subscribe Protocol...")
    for x in range(5):  # Aumentado para 5 carros
        car = CarAgent(f"carro_{x}@localhost", "pass", environment)
        await car.start(auto_register=True)

    print("\n" + "=" * 80)
    print("SISTEMA INICIADO!")
    print("=" * 80)
    print("\nComportamentos esperados:")
    print("  • Carros normais subscrevem semáforos automaticamente")
    print("  • Carros recebem notificações quando semáforos mudam")
    print("  • Veículos de emergência surgem a cada 10s e solicitam luz verde")
    print("  • MapUpdater analisa congestionamento a cada 25s")
    print("  • Semáforos respondem com AGREE/INFORM/FAILURE conforme protocolo FIPA")
    print("=" * 80 + "\n")

    try:
        while True:
            environment.update_map()
            await asyncio.sleep(0)
    except KeyboardInterrupt:
        print("\n" + "=" * 80)
        print("ENCERRANDO SIMULAÇÃO...")
        print("=" * 80)

        # Guarda dados
        environment.write_on_csv(environment.cars_stopped_times)

        # Para todos os agentes SPADE
        print("Parando agentes...")
        for tl in tl_agents:
            await tl.stop()
        await map_updater.stop()
        # (carros param automaticamente quando o loop termina)

        pygame.quit()
        print("Sistema encerrado com sucesso!")


if __name__ == "__main__":
    spade.run(main())