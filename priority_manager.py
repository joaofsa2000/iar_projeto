# priority_manager.py
import asyncio, random, time
from spade import agent, behaviour
from spade.message import Message
import traci
from utils import parse_net_file

SUMO_PORT = 8813
NET = parse_net_file()
EDGES = NET["edges"]

LABEL = "pm"
ORDER = 3    # se tiveres 3 clientes: usa 1,2,3 por exemplo; ajusta conforme o traffic agent

PRIO_TYPES = {
    "ambulance": {"typeID": "ambulance", "maxSpeed": 20.0},
    "police": {"typeID": "police", "maxSpeed": 20.0},
    "fire": {"typeID": "fire", "maxSpeed": 20.0},
}

TRAFFIC_JID = "traffic_light_manager@localhost"

def ensure_connection(port=8813, label=LABEL, order=ORDER):
    while True:
        try:
            traci.init(port, label=label)
            traci.setOrder(order)
            print(f"[PriorityManager] Ligado ao TraCI (label={label}, order={order}) na porta {port}")
            break
        except Exception as e:
            print(f"[PriorityManager] Ainda sem ligação ({e}) — a tentar de novo em 1s...")
            time.sleep(1)

class PriorityManager(agent.Agent):
    class SpawnBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            # passo de simulação (multi-client)
            try:
                traci.simulationStep()
            except Exception:
                pass

            if random.random() < 0.08:
                vid = f"prio_{int(time.time()*1000)%100000}-{random.randint(0,999)}"
                ptype = random.choice(list(PRIO_TYPES.keys()))
                route = random.choice([EDGES, EDGES[::-1]])[:random.randint(1,3)]
                rid = f"r_{vid}"
                try:
                    traci.route.add(rid, route)
                    traci.vehicle.add(vid, rid, typeID=PRIO_TYPES[ptype]["typeID"])
                    traci.vehicle.setMaxSpeed(vid, PRIO_TYPES[ptype]["maxSpeed"])
                    try:
                        traci.vehicle.setEmergency(vid, True)
                    except Exception:
                        pass
                    print(f"[PriorityManager] Spawned PRIORITY {ptype} {vid} route {route}")

                    await asyncio.sleep(0.5)
                    pos = traci.vehicle.getPosition(vid)
                    msg = Message(to=TRAFFIC_JID)
                    msg.body = f"PRIORITY_REQ {vid} {pos[0]:.2f} {pos[1]:.2f}"
                    await self.send(msg)
                    print(f"[PriorityManager] Sent PRIORITY_REQ for {vid} to {TRAFFIC_JID}")
                except Exception as e:
                    print("[PriorityManager] erro ao spawn/prioridade:", e)

            await asyncio.sleep(1.0)

    async def setup(self):
        print(f"[{self.name}] PriorityManager iniciado.")
        ensure_connection(SUMO_PORT, LABEL, ORDER)
        self.add_behaviour(self.SpawnBehaviour())

if __name__=="__main__":
    async def main():
        pm = PriorityManager("priority_manager@localhost", "password")
        await pm.start()
        print("PriorityManager iniciado (CTRL+C para sair).")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await pm.stop()
            try:
                traci.close()
            except Exception:
                pass

    asyncio.run(main())
