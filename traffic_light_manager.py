# traffic_light_manager.py
# Controla semáforos. Aceita pedidos SPADE do PriorityManager com a mensagem:
# "PRIORITY_REQ <veh_id> <x> <y>"
# Ao receber um pedido, identifica o tl mais próximo e força (temporariamente)
# uma fase "verde para prioridade" (implementação simples: faz 'G' para todos links
# do TLS durante X segundos) e depois restaura o estado anterior.

import asyncio, time
from spade import agent, behaviour
from spade.message import Message
import traci
from utils import parse_net_file, dist

SUMO_PORT = 8813
NET = parse_net_file()
TL_IDS = NET["tls"]

PRIORITY_GREEN_DURATION = 8.0  # segundos que o semáforo fica em estado "prioridade"

class TrafficLightManager(agent.Agent):
    class ControlBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            # garante ligação Traci
            try:
                traci.init(port=SUMO_PORT)
            except Exception:
                pass

            # escuta mensagens PRIORITY_REQ
            msg = await self.receive(timeout=0.1)
            if msg:
                body = msg.body.strip()
                if body.startswith("PRIORITY_REQ"):
                    parts = body.split()
                    if len(parts) >= 4:
                        _, vid, sx, sy = parts[:4]
                        sx, sy = float(sx), float(sy)
                        print(f"[TrafficLightManager] Received priority request from {vid} pos=({sx},{sy})")
                        # encontra tl mais próximo (usa posição do junction via traci)
                        best_tl = None
                        best_d = float("inf")
                        for tl in TL_IDS:
                            try:
                                pos = traci.junction.getPosition(tl)
                            except Exception:
                                # nem todos os tlLogic têm junct id correspondentes para traci.junction
                                # fallback: tentar ler controlled link coords (skip here)
                                pos = None
                            if pos:
                                d = dist((sx,sy), pos)
                                if d < best_d:
                                    best_d = d
                                    best_tl = tl
                        if best_tl:
                            print(f"[TrafficLightManager] Closest TL {best_tl} at distance {best_d:.1f}")
                            # guarda estado atual (fase e estado string) e aplica "verde total" temporário
                            try:
                                nlinks = len(traci.trafficlight.getControlledLinks(best_tl))
                                green_state = "G" * nlinks
                                # guarda a actual state (string) e phase index
                                old_state = traci.trafficlight.getRedYellowGreenState(best_tl)
                                old_phase = traci.trafficlight.getPhase(best_tl)
                                traci.trafficlight.setRedYellowGreenState(best_tl, green_state)
                                print(f"[TrafficLightManager] Set {best_tl} to priority (all-green) for {PRIORITY_GREEN_DURATION}s")
                                # aguarda durante duration (não bloqueante para o resto do agente)
                                await asyncio.sleep(PRIORITY_GREEN_DURATION)
                                # restaura fase anterior (poderá ter sido alterada externamente)
                                traci.trafficlight.setPhase(best_tl, old_phase)
                                traci.trafficlight.setRedYellowGreenState(best_tl, old_state)
                                print(f"[TrafficLightManager] Restored TLS {best_tl}")
                            except Exception as e:
                                print(f"[TrafficLightManager] Erro ao aplicar prioridade em {best_tl}: {e}")
                        else:
                            print("[TrafficLightManager] Nenhum TL encontrado para prioritizar.")
            # pequena pausa para ceder CPU
            await asyncio.sleep(0.1)

    async def setup(self):
        print(f"[{self.name}] TrafficLightManager iniciado. TLS detectados:", TL_IDS)
        self.add_behaviour(self.ControlBehaviour())

if __name__ == "__main__":
    async def main():
        tm = TrafficLightManager("traffic_light_manager@localhost", "password")
        await tm.start()
        print("TrafficLightManager iniciado (CTRL+C para sair).")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await tm.stop()
            try:
                traci.close()
            except Exception:
                pass

    asyncio.run(main())