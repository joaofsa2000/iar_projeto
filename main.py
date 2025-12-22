import asyncio
import pygame
import spade

# Importar os novos agentes com protocolos FIPA
from Agents.CarAgent import CarAgent
from Agents.MapUpdaterAgent import MapUpdaterAgent
from Agents.TrafficLightAgent import TrafficLightAgent
from Agents.EmergencyCarAgent import EmergencyCarAgent
from Agents.ChaosAgent import ChaosAgent

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

    # Cria o ambiente (fullscreen=True para ecrã inteiro com vsync)
    # Use fullscreen=False para modo janela
    environment = Environment(fullscreen=True)

    # Cria e inicia o agente central (MapUpdater)
    print("[SETUP] Iniciando agente central (MapUpdater)...")
    num_initial_cars = 30  # Número de carros iniciais (aumentado)
    map_updater = MapUpdaterAgent("central@localhost", "pass", environment, initial_car_count=num_initial_cars)
    await map_updater.start(auto_register=True)
    
    # Cria e inicia o Chaos Agent (gerencia perturbações automaticamente)
    print("[SETUP] Iniciando Chaos Agent (gerenciamento de perturbações)...")
    chaos_agent = ChaosAgent("chaos@localhost", "pass", environment)
    await chaos_agent.start(auto_register=True)
    environment.set_chaos_agent_jid("chaos@localhost")
    
    # Definição dos semáforos
    # NOTA: CrossingTrafficLightModel espera: (id, bottom_tl, top_tl, left_tl, right_tl)
    # - bottom_tl: semáforos no lado inferior (ângulo 0°, controlam tráfego vindo de baixo)
    # - top_tl: semáforos no lado superior (ângulo 180°, controlam tráfego vindo de cima)
    # - left_tl: semáforos no lado esquerdo (ângulo -90°, controlam tráfego vindo da esquerda)
    # - right_tl: semáforos no lado direito (ângulo 90°, controlam tráfego vindo da direita)
    #
    # Sincronização de pares:
    # - VERTICAL (top + bottom): Controlam tráfego norte-sul
    # - HORIZONTAL (left + right): Controlam tráfego este-oeste
    print("[SETUP] Configurando semáforos...")

    # ============================================================
    # CRUZAMENTO 1 - bottom_left
    # ============================================================
    tl_1_disposition = CrossingTrafficLightModel(
        "bottom_left",
        # bottom_tl - lado inferior (ângulo 0°) - controla tráfego vindo do sul
        SideTrafficLightModel(
            TrafficLightModel((278, 621), 0, LightStatus.RED),
            TrafficLightModel((300, 621), 0, LightStatus.RED),
            TrafficLightModel((322, 621), 0, LightStatus.RED),
        ),
        # top_tl - lado superior (ângulo 180°) - controla tráfego vindo do norte
        SideTrafficLightModel(
            TrafficLightModel((256, 442), 180, LightStatus.RED),
            TrafficLightModel((234, 442), 180, LightStatus.RED),
            TrafficLightModel((212, 442), 180, LightStatus.RED),
        ),
        # left_tl - lado esquerdo (ângulo -90°) - controla tráfego vindo do oeste
        SideTrafficLightModel(
            TrafficLightModel((178, 542), -90, LightStatus.RED),
            TrafficLightModel((178, 564), -90, LightStatus.RED),
            TrafficLightModel((178, 586), -90, LightStatus.RED),
        ),
        # right_tl - lado direito (ângulo 90°) - controla tráfego vindo do este
        SideTrafficLightModel(
            TrafficLightModel((357, 519), 90, LightStatus.RED),
            TrafficLightModel((357, 497), 90, LightStatus.RED),
            TrafficLightModel((357, 475), 90, LightStatus.RED),
        ),
    )

    # ============================================================
    # CRUZAMENTO 2 - bottom_mid
    # ============================================================
    tl_2_disposition = CrossingTrafficLightModel(
        "bottom_mid",
        # bottom_tl - lado inferior (ângulo 0°)
        SideTrafficLightModel(
            TrafficLightModel((637, 621), 0, LightStatus.RED),
            TrafficLightModel((659, 621), 0, LightStatus.RED),
            TrafficLightModel((681, 621), 0, LightStatus.RED),
        ),
        # top_tl - lado superior (ângulo 180°)
        SideTrafficLightModel(
            TrafficLightModel((616, 442), 180, LightStatus.RED),
            TrafficLightModel((594, 442), 180, LightStatus.RED),
            TrafficLightModel((572, 442), 180, LightStatus.RED),
        ),
        # left_tl - lado esquerdo (ângulo -90°)
        SideTrafficLightModel(
            TrafficLightModel((537, 541), -90, LightStatus.RED),
            TrafficLightModel((537, 563), -90, LightStatus.RED),
            TrafficLightModel((537, 586), -90, LightStatus.RED),
        ),
        # right_tl - lado direito (ângulo 90°)
        SideTrafficLightModel(
            TrafficLightModel((717, 519), 90, LightStatus.RED),
            TrafficLightModel((717, 497), 90, LightStatus.RED),
            TrafficLightModel((717, 474), 90, LightStatus.RED),
        ),
    )

    # ============================================================
    # CRUZAMENTO 3 - bottom_right
    # ============================================================
    tl_3_disposition = CrossingTrafficLightModel(
        "bottom_right",
        # bottom_tl - lado inferior (ângulo 0°)
        SideTrafficLightModel(
            TrafficLightModel((1002, 621), 0, LightStatus.RED),
            TrafficLightModel((1024, 621), 0, LightStatus.RED),
            TrafficLightModel((1046, 621), 0, LightStatus.RED),
        ),
        # top_tl - lado superior (ângulo 180°)
        SideTrafficLightModel(
            TrafficLightModel((981, 442), 180, LightStatus.RED),
            TrafficLightModel((959, 442), 180, LightStatus.RED),
            TrafficLightModel((937, 442), 180, LightStatus.RED),
        ),
        # left_tl - lado esquerdo (ângulo -90°)
        SideTrafficLightModel(
            TrafficLightModel((902, 541), -90, LightStatus.RED),
            TrafficLightModel((902, 563), -90, LightStatus.RED),
            TrafficLightModel((902, 585), -90, LightStatus.RED),
        ),
        # right_tl - lado direito (ângulo 90°)
        SideTrafficLightModel(
            TrafficLightModel((1082, 519), 90, LightStatus.RED),
            TrafficLightModel((1082, 497), 90, LightStatus.RED),
            TrafficLightModel((1082, 475), 90, LightStatus.RED),
        ),
    )

    # ============================================================
    # CRUZAMENTO 4 - top_left
    # ============================================================
    tl_4_disposition = CrossingTrafficLightModel(
        "top_left",
        # bottom_tl - lado inferior (ângulo 0°)
        SideTrafficLightModel(
            TrafficLightModel((278, 271), 0, LightStatus.RED),
            TrafficLightModel((300, 271), 0, LightStatus.RED),
            TrafficLightModel((322, 271), 0, LightStatus.RED),
        ),
        # top_tl - lado superior (ângulo 180°)
        SideTrafficLightModel(
            TrafficLightModel((256, 92), 180, LightStatus.RED),
            TrafficLightModel((234, 92), 180, LightStatus.RED),
            TrafficLightModel((212, 92), 180, LightStatus.RED),
        ),
        # left_tl - lado esquerdo (ângulo -90°)
        SideTrafficLightModel(
            TrafficLightModel((178, 191), -90, LightStatus.RED),
            TrafficLightModel((178, 213), -90, LightStatus.RED),
            TrafficLightModel((178, 235), -90, LightStatus.RED),
        ),
        # right_tl - lado direito (ângulo 90°)
        SideTrafficLightModel(
            TrafficLightModel((358, 169), 90, LightStatus.RED),
            TrafficLightModel((358, 147), 90, LightStatus.RED),
            TrafficLightModel((358, 125), 90, LightStatus.RED),
        ),
    )

    # ============================================================
    # CRUZAMENTO 5 - top_mid
    # ============================================================
    tl_5_disposition = CrossingTrafficLightModel(
        "top_mid",
        # bottom_tl - lado inferior (ângulo 0°)
        SideTrafficLightModel(
            TrafficLightModel((637, 271), 0, LightStatus.RED),
            TrafficLightModel((659, 271), 0, LightStatus.RED),
            TrafficLightModel((681, 271), 0, LightStatus.RED),
        ),
        # top_tl - lado superior (ângulo 180°)
        SideTrafficLightModel(
            TrafficLightModel((615, 92), 180, LightStatus.RED),
            TrafficLightModel((593, 92), 180, LightStatus.RED),
            TrafficLightModel((571, 92), 180, LightStatus.RED),
        ),
        # left_tl - lado esquerdo (ângulo -90°)
        SideTrafficLightModel(
            TrafficLightModel((537, 191), -90, LightStatus.RED),
            TrafficLightModel((537, 213), -90, LightStatus.RED),
            TrafficLightModel((537, 235), -90, LightStatus.RED),
        ),
        # right_tl - lado direito (ângulo 90°)
        SideTrafficLightModel(
            TrafficLightModel((717, 169), 90, LightStatus.RED),
            TrafficLightModel((717, 147), 90, LightStatus.RED),
            TrafficLightModel((717, 125), 90, LightStatus.RED),
        ),
    )

    # ============================================================
    # CRUZAMENTO 6 - top_right
    # ============================================================
    tl_6_disposition = CrossingTrafficLightModel(
        "top_right",
        # bottom_tl - lado inferior (ângulo 0°)
        SideTrafficLightModel(
            TrafficLightModel((1002, 271), 0, LightStatus.RED),
            TrafficLightModel((1024, 271), 0, LightStatus.RED),
            TrafficLightModel((1046, 271), 0, LightStatus.RED),
        ),
        # top_tl - lado superior (ângulo 180°)
        SideTrafficLightModel(
            TrafficLightModel((980, 92), 180, LightStatus.RED),
            TrafficLightModel((958, 92), 180, LightStatus.RED),
            TrafficLightModel((936, 92), 180, LightStatus.RED),
        ),
        # left_tl - lado esquerdo (ângulo -90°)
        SideTrafficLightModel(
            TrafficLightModel((902, 191), -90, LightStatus.RED),
            TrafficLightModel((902, 213), -90, LightStatus.RED),
            TrafficLightModel((902, 235), -90, LightStatus.RED),
        ),
        # right_tl - lado direito (ângulo 90°)
        SideTrafficLightModel(
            TrafficLightModel((1082, 169), 90, LightStatus.RED),
            TrafficLightModel((1082, 147), 90, LightStatus.RED),
            TrafficLightModel((1082, 125), 90, LightStatus.RED),
        ),
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
    for x in range(num_initial_cars):
        car = CarAgent(f"carro_{x}@localhost", "pass", environment)
        await car.start(auto_register=True)

    print("\n" + "=" * 80)
    print("SISTEMA INICIADO!")
    print("=" * 80)
    print("\nComportamentos esperados:")
    print("  • Carros normais subscrevem semáforos automaticamente")
    print("  • Carros recebem notificações quando semáforos mudam (VERDE/AMARELO/VERMELHO)")
    print("  • Novos carros spawn continuamente baseado na densidade de tráfego")
    print("  • Veículos de emergência surgem a cada 15s e solicitam luz verde")
    print("  • MapUpdater analisa congestionamento a cada 25s")
    print("  • Semáforos funcionam em pares sincronizados:")
    print("      - VERTICAL (cima + baixo): Tráfego norte-sul")
    print("      - HORIZONTAL (esquerda + direita): Tráfego este-oeste")
    print("  • Carros solicitam luz verde após 30s de espera")
    print("  • Semáforos respondem com AGREE/INFORM/FAILURE conforme protocolo FIPA")
    print("  • Carros usam algoritmo A* para calcular rotas")
    print("  • Sistema de negociação para resolver deadlocks em cruzamentos")
    print("=" * 80 + "\n")

    try:
        while True:
            environment.update_map()
            await asyncio.sleep(0)
    except KeyboardInterrupt:
        print("\n" + "=" * 80)
        print("ENCERRANDO SIMULAÇÃO...")
        print("=" * 80)

        # Guarda dados de espera
        print("Guardando dados de tempos de espera...")
        environment.write_on_csv(environment.cars_stopped_times)

        # Para todos os agentes SPADE de forma ordenada
        print("Parando agentes de semáforos...")
        for tl in tl_agents:
            try:
                await tl.stop()
            except Exception as e:
                print(f"Erro ao parar semáforo: {e}")

        print("Parando agente central...")
        try:
            await map_updater.stop()
        except Exception as e:
            print(f"Erro ao parar map updater: {e}")
        
        print("Parando Chaos Agent...")
        try:
            await chaos_agent.stop()
        except Exception as e:
            print(f"Erro ao parar chaos agent: {e}")

        # Guardar todas as métricas para análise futura e treino de modelos
        print("\nGuardando métricas para análise e ML...")
        environment.save_all_metrics()
        
        # Estatísticas da simulação (usando métricas avançadas)
        environment.print_metrics_summary()

        # Pygame
        pygame.quit()
        print("\nSistema encerrado com sucesso!")


if __name__ == "__main__":
    spade.run(main())
