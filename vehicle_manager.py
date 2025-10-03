# vehicle_manager.py
import asyncio, random, time
from spade import agent, behaviour
import traci
from utils import parse_net_file

SUMO_PORT = 8813
NET = parse_net_file()
EDGES = NET["edges"]

LABEL = "vm"     # label único para esta conexão
ORDER = 2        # ordem no multi-client (0..N-1)

VEHTYPES = {
    "car": {"typeID": "car", "maxSpeed": 13.9},
    "bus": {"typeID": "bus", "maxSpeed": 8.0},
    "moto": {"typeID": "motorcycle", "maxSpeed": 18.0},
}

def sample_routes(edges, n=10):
    routes = []
    for i in range(n):
        length = random.choice([2,3,4])
        if len(edges) >= length:
            start = random.randint(0, len(edges)-length)
            route = edges[start:start+length]
            routes.append(route)
    if not routes and edges:
        routes = [[e] for e in edges]
    return routes

POSSIBLE_ROUTES = sample_routes(EDGES, n=30)

def ensure_connection(port=8813, label=LABEL, order=ORDER):
    """Tenta conectar até ter sucesso; define o order (obrigatório em multi-client)."""
    while True:
        try:
            # label permite distinguir conexões em setups multi-client
            traci.init(port, label=label)
            # setOrder deve ser enviado como primeiro comando após conectar
            traci.setOrder(order)
            print(f"[VehicleManager] Ligado ao TraCI (label={label}, order={order}) na porta {port}")
            break
        except Exception as e:
            print(f"[VehicleManager] Não ligado ainda ({e}), a tentar de novo em 1s...")
            time.sleep(1)

class VehicleManager(agent.Agent):
    class GeneratorBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            # Em ambiente multi-client: cada cliente envia simulationStep()
            try:
                traci.simulationStep()
            except Exception:
                # se algo falhar, ignorar e continuar (ligação pode cair/recuperar)
                pass

            # criar veículo aleatório
            if random.random() < 0.6:
                vid = f"veh_{int(time.time()*1000)%100000}-{random.randint(0,999)}"
                vtype = random.choice(list(VEHTYPES.keys()))
                route = random.choice(POSSIBLE_ROUTES)
                route_id = f"r_{vid}"
                try:
                    traci.route.add(route_id, route)
                    traci.vehicle.add(vid, route_id, typeID=VEHTYPES[vtype]["typeID"])
                    traci.vehicle.setMaxSpeed(vid, VEHTYPES[vtype]["maxSpeed"])
                    print(f"[VehicleManager] Spawned {vtype} {vid} on {route}")
                except Exception as e:
                    print("[VehicleManager] erro ao spawn:", e)

            await asyncio.sleep(random.uniform(0.6, 2.0))

    async def setup(self):
        print(f"[{self.name}] VehicleManager iniciado.")
        ensure_connection(SUMO_PORT, LABEL, ORDER)
        self.add_behaviour(self.GeneratorBehaviour())

if __name__=="__main__":
    async def main():
        vm = VehicleManager("vehicle_manager@localhost", "password")
        await vm.start()
        print("VehicleManager iniciado (CTRL+C para sair).")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await vm.stop()
            try:
                traci.close()
            except Exception:
                pass

    asyncio.run(main())
