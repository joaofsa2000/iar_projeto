# city_three_agents.py
import asyncio
import math
import random
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Optional

import pygame
from spade import agent, behaviour, message, template

###############################################################################
# CONFIG: 1 utilizador por agente
###############################################################################

JID_TRAFFIC = "agent1@localhost"   # controlador de semáforos
PW_TRAFFIC  = "12345"

JID_CAR     = "agent2@localhost"   # 1 carro normal
PW_CAR      = "12345"

JID_EMERG   = "emerg@localhost"    # viatura(s) de emergência (cria no XMPP)
PW_EMERG    = "12345"

TIMINGS = dict(green=6.0, yellow=2.0, red_buffer=0.0, preempt=6.0)

###############################################################################
# Modelo partilhado (render lê; agentes escrevem)
###############################################################################

@dataclass
class TrafficLightState:
    id: str
    pos: Tuple[int, int]       # centro (x, y)
    orientation: str           # "NS" ou "EW"
    state: str = "VERMELHO"    # "VERDE"|"AMARELO"|"VERMELHO"

@dataclass
class CarState:
    id: str
    pos: List[float]           # [x, y]
    dir: Tuple[float, float]   # vetor direcional normalizado
    speed: float               # px/s
    target: Tuple[int, int]    # próximo waypoint (x, y)
    kind: str = "normal"       # "normal" | "emergency"

@dataclass
class SharedWorld:
    lock: threading.Lock = field(default_factory=threading.Lock)
    lights: Dict[str, TrafficLightState] = field(default_factory=dict)  # L{idx}{NS|EW}
    cars: Dict[str, CarState] = field(default_factory=dict)             # C0, E0, ...

WORLD = SharedWorld()

###############################################################################
# Helpers geom e waypoints
###############################################################################

WIDTH, HEIGHT = 960, 640
LANE = 24
ROADS_X = [WIDTH//3, 2*WIDTH//3]
ROADS_Y = [HEIGHT//3, 2*HEIGHT//3]

def dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0]-b[0], a[1]-b[1])

def normalize(vx: float, vy: float) -> Tuple[float, float]:
    m = math.hypot(vx, vy)
    if m == 0: return (0.0, 0.0)
    return (vx/m, vy/m)

def next_waypoint_loop(current: Tuple[int, int]) -> Tuple[int, int]:
    ring = [
        (ROADS_X[0]-LANE, ROADS_Y[0]-2),
        (ROADS_X[1]+LANE, ROADS_Y[0]-2),
        (ROADS_X[1]+LANE, ROADS_Y[1]+LANE),
        (ROADS_X[0]-LANE, ROADS_Y[1]+LANE),
    ]
    for i, p in enumerate(ring):
        if dist(p, current) < 4:
            return ring[(i+1) % len(ring)]
    return min(ring, key=lambda p: dist(p, current))

def orientation_from_dir(d: Tuple[float,float]) -> str:
    # aproximação: vertical dominante -> NS, senão EW
    return "NS" if abs(d[1]) >= abs(d[0]) else "EW"

def nearest_intersection_ahead(pos: Tuple[float,float], dirv: Tuple[float,float]) -> Optional[int]:
    # devolve índice 0..3 da interseção mais próxima À FRENTE (projeção positiva)
    best_idx, best_d = None, 1e9
    intersections = [(ROADS_X[0], ROADS_Y[0]), (ROADS_X[1], ROADS_Y[0]),
                     (ROADS_X[1], ROADS_Y[1]), (ROADS_X[0], ROADS_Y[1])]
    for idx, L in enumerate(intersections):
        v = (L[0]-pos[0], L[1]-pos[1])
        ahead = v[0]*dirv[0] + v[1]*dirv[1]
        if ahead > 0:
            d = dist(pos, L)
            if d < best_d:
                best_idx, best_d = idx, d
    return best_idx

###############################################################################
# Mundo inicial
###############################################################################

def build_world():
    with WORLD.lock:
        WORLD.lights.clear()
        lid = 0
        for rx in ROADS_X:
            for ry in ROADS_Y:
                WORLD.lights[f"L{lid}NS"] = TrafficLightState(id=f"L{lid}NS", pos=(rx, ry-18), orientation="NS")
                WORLD.lights[f"L{lid}EW"] = TrafficLightState(id=f"L{lid}EW", pos=(rx-18, ry), orientation="EW")
                lid += 1

        WORLD.cars.clear()
        # C0 = carro normal (controlado pelo CarAgent)
        sp = (ROADS_X[0]-LANE, ROADS_Y[0]-2)
        tgt = (ROADS_X[1]+LANE, ROADS_Y[0]-2)
        d = normalize(tgt[0]-sp[0], tgt[1]-sp[1])
        WORLD.cars["C0"] = CarState(id="C0", pos=[float(sp[0]), float(sp[1])], dir=d,
                                    speed=85.0, target=tgt, kind="normal")
        # E0 = emergência (controlada pelo EmergencyAgent)
        spE = (ROADS_X[0]-LANE, ROADS_Y[1]+LANE)
        tgtE = (ROADS_X[1]+LANE, ROADS_Y[1]+LANE)
        dE = normalize(tgtE[0]-spE[0], tgtE[1]-spE[1])
        WORLD.cars["E0"] = CarState(id="E0", pos=[float(spE[0]), float(spE[1])], dir=dE,
                                    speed=140.0, target=tgtE, kind="emergency")

###############################################################################
# Agente de Semáforos (Controlador central com pré-emção)
###############################################################################

class TrafficControllerAgent(agent.Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # preemptions: idx_intersec -> (orientation, end_time)
        self.preemptions: Dict[int, Tuple[str, float]] = {}

    def _apply_cycle_state(self, open_orientation: str):
        # define estados base para todo o mapa (salvo interseções em pré-emção)
        with WORLD.lock:
            # primeiro fecha tudo
            for l in WORLD.lights.values():
                l.state = "VERMELHO"
            # abre orientação pedida
            for l in WORLD.lights.values():
                if l.orientation == open_orientation:
                    l.state = "VERDE"
            # aplica pré-emções por cima
            now = time.time()
            to_delete = []
            for idx, (ori, until) in self.preemptions.items():
                if now >= until:
                    to_delete.append(idx)
                    continue
                # força o par dessa interseção
                # ids válidos: L{idx}NS e L{idx}EW
                lid_ns = f"L{idx}NS"
                lid_ew = f"L{idx}EW"
                if lid_ns in WORLD.lights and lid_ew in WORLD.lights:
                    WORLD.lights[lid_ns].state = "VERDE" if ori == "NS" else "VERMELHO"
                    WORLD.lights[lid_ew].state = "VERDE" if ori == "EW" else "VERMELHO"
            for idx in to_delete:
                del self.preemptions[idx]

    class CycleBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            # ciclo base: abre NS, amarelo, abre EW, amarelo — mas respeita pré-emções ativas
            tG, tY = TIMINGS["green"], TIMINGS["yellow"]

            # NS verde
            self.agent._apply_cycle_state("NS")
            await asyncio.sleep(tG)
            # NS amarelo (apenas luzes NS)
            with WORLD.lock:
                for l in WORLD.lights.values():
                    if l.orientation == "NS" and l.state == "VERDE":
                        l.state = "AMARELO"
            await asyncio.sleep(tY)

            # EW verde
            self.agent._apply_cycle_state("EW")
            await asyncio.sleep(tG)
            # EW amarelo
            with WORLD.lock:
                for l in WORLD.lights.values():
                    if l.orientation == "EW" and l.state == "VERDE":
                        l.state = "AMARELO"
            await asyncio.sleep(tY)

    class RespondBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=0.1)
            if not msg:
                return
            parts = msg.body.split()
            if not parts:
                return

            # STATE_REQ x y dx dy
            if parts[0] == "STATE_REQ" and len(parts) >= 5:
                _, sx, sy, sdx, sdy = parts[:5]
                car_pos = (float(sx), float(sy))
                car_dir = normalize(float(sdx), float(sdy))
                best, best_d = None, 1e9
                with WORLD.lock:
                    # escolhe semáforo mais próximo à frente
                    for k, l in WORLD.lights.items():
                        v = (l.pos[0]-car_pos[0], l.pos[1]-car_pos[1])
                        ahead = v[0]*car_dir[0] + v[1]*car_dir[1]
                        if ahead > 0:
                            d = dist(car_pos, l.pos)
                            if d < best_d:
                                best, best_d = l, d
                if best:
                    reply = f"STATE_REP {best.id} {best.state} {best.pos[0]} {best.pos[1]}"
                else:
                    reply = "STATE_REP NONE NONE 0 0"
                await self.send(message.Message(to=str(msg.sender), body=reply))

            # PREEMPT_REQ idx orientation seconds
            elif parts[0] == "PREEMPT_REQ" and len(parts) >= 4:
                _, sidx, ori, ssec = parts[:4]
                idx = int(sidx)
                sec = float(ssec)
                until = time.time() + sec
                # regista pré-emção
                self.agent.preemptions[idx] = (ori, until)
                # aplica imediatamente (não espera próximo passo do ciclo)
                self.agent._apply_cycle_state(open_orientation="NS" if ori=="NS" else "EW")
                await self.send(message.Message(to=str(msg.sender), body="PREEMPT_ACK"))

    async def setup(self):
        print(f"[{self.name}] TrafficController iniciado.")
        self.add_behaviour(self.CycleBehaviour())
        self.add_behaviour(self.RespondBehaviour(), template.Template())

###############################################################################
# Agente do Carro (1 carro normal)
###############################################################################

class CarAgent(agent.Agent):
    TRAFFIC_JID = JID_TRAFFIC

    class DriveBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            dt = 0.05
            car = None
            with WORLD.lock:
                car = WORLD.cars.get("C0")
            if not car:
                await asyncio.sleep(dt); return

            # perto de interseção?
            near = False
            with WORLD.lock:
                near = any(dist(car.pos, l.pos) < 100 for l in WORLD.lights.values())

            if near:
                req = message.Message(
                    to=self.agent.TRAFFIC_JID,
                    body=f"STATE_REQ {car.pos[0]} {car.pos[1]} {car.dir[0]} {car.dir[1]}",
                )
                await self.send(req)
                rep = await self.receive(timeout=0.05)
                allow = True
                if rep and rep.body.startswith("STATE_REP"):
                    _, lid, state, lx, ly = rep.body.split()[:5]
                    if lid != "NONE":
                        if state in ("VERMELHO","AMARELO") and dist(car.pos, (float(lx), float(ly))) < 60:
                            allow = False
                if allow:
                    car.pos[0] += car.dir[0]*car.speed*dt
                    car.pos[1] += car.dir[1]*car.speed*dt
            else:
                car.pos[0] += car.dir[0]*car.speed*dt
                car.pos[1] += car.dir[1]*car.speed*dt

            # waypoint
            if dist(car.pos, car.target) < 8:
                car.target = next_waypoint_loop(car.target)
                car.dir = normalize(car.target[0]-car.pos[0], car.target[1]-car.pos[1])

            await asyncio.sleep(dt)

    async def setup(self):
        print(f"[{self.name}] CarAgent iniciado (1 carro).")
        self.add_behaviour(self.DriveBehaviour())

###############################################################################
# Agente de Emergência (pré-emção de semáforos)
###############################################################################

class EmergencyAgent(agent.Agent):
    TRAFFIC_JID = JID_TRAFFIC

    class DriveBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            dt = 0.05
            car = None
            with WORLD.lock:
                car = WORLD.cars.get("E0")
            if not car:
                await asyncio.sleep(dt); return

            # quando a < 130px de um cruzamento à frente, pedir PREEMPT
            idx = nearest_intersection_ahead(tuple(car.pos), car.dir)
            if idx is not None:
                # calcular distância ao centro da interseção (ponto médio dos dois marcadores)
                intersections = [(ROADS_X[0], ROADS_Y[0]), (ROADS_X[1], ROADS_Y[0]),
                                 (ROADS_X[1], ROADS_Y[1]), (ROADS_X[0], ROADS_Y[1])]
                L = intersections[idx]
                if dist(car.pos, L) < 130:
                    ori = orientation_from_dir(car.dir)
                    req = message.Message(
                        to=self.agent.TRAFFIC_JID,
                        body=f"PREEMPT_REQ {idx} {ori} {TIMINGS['preempt']}",
                    )
                    await self.send(req)
                    # não precisamos de esperar o ACK para avançar

            # mesmo assim, confirmar estado para não travar desnecessariamente
            req_state = message.Message(
                to=self.agent.TRAFFIC_JID,
                body=f"STATE_REQ {car.pos[0]} {car.pos[1]} {car.dir[0]} {car.dir[1]}",
            )
            await self.send(req_state)
            rep = await self.receive(timeout=0.05)
            allow = True
            if rep and rep.body.startswith("STATE_REP"):
                _, lid, state, lx, ly = rep.body.split()[:5]
                if lid != "NONE":
                    if state in ("VERMELHO","AMARELO") and dist(car.pos, (float(lx), float(ly))) < 50:
                        # emergência tende a reduzir menos, mas ainda assim evitar colisão
                        allow = False

            speed_factor = 1.1 if allow else 0.2  # emergência acelera mais quando tem via livre
            car.pos[0] += car.dir[0]*car.speed*dt*speed_factor
            car.pos[1] += car.dir[1]*car.speed*dt*speed_factor

            # waypoint
            if dist(car.pos, car.target) < 8:
                car.target = next_waypoint_loop(car.target)
                car.dir = normalize(car.target[0]-car.pos[0], car.target[1]-car.pos[1])

            await asyncio.sleep(dt)

    async def setup(self):
        print(f"[{self.name}] EmergencyAgent iniciado (viaturas de emergência).")
        self.add_behaviour(self.DriveBehaviour())

###############################################################################
# Render (Pygame)
###############################################################################

def draw_world(screen, font):
    screen.fill((30, 30, 35))
    road_color = (60, 60, 60)
    for rx in ROADS_X:
        pygame.draw.rect(screen, road_color, pygame.Rect(rx-LANE, 0, 2*LANE, HEIGHT))
    for ry in ROADS_Y:
        pygame.draw.rect(screen, road_color, pygame.Rect(0, ry-LANE, WIDTH, 2*LANE))

    with WORLD.lock:
        lights = list(WORLD.lights.values())
        cars = list(WORLD.cars.values())

    for l in lights:
        color = (90, 200, 90) if l.state == "VERDE" else (220, 200, 90) if l.state == "AMARELO" else (220, 90, 90)
        pygame.draw.circle(screen, color, l.pos, 8)

    for c in cars:
        rect = pygame.Rect(0, 0, 26 if c.kind=="emergency" else 24, 14 if c.kind=="emergency" else 12)
        rect.center = (int(c.pos[0]), int(c.pos[1]))
        color = (255, 160, 60) if c.kind=="emergency" else (160, 200, 255)
        pygame.draw.rect(screen, color, rect)
        tip = (c.pos[0] + c.dir[0]*14, c.pos[1] + c.dir[1]*14)
        pygame.draw.line(screen, (235, 235, 235), (c.pos[0], c.pos[1]), tip, 2)
        if c.kind == "emergency":
            # pequeno “giroflex”: quadradinho que alterna opacidade
            if (pygame.time.get_ticks()//200)%2==0:
                gf = pygame.Rect(0,0,10,6); gf.midbottom = rect.midtop
                pygame.draw.rect(screen, (240,240,255), gf)

    text = font.render("Semáforos (agent1) | Carro (agent2) | Emergência (emerg) — ESC para sair", True, (220,220,220))
    screen.blit(text, (12, 8))

def run_pygame(stop_event: threading.Event):
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Cidade Multi-Agente (3 agentes: Carro, Semáforos, Emergência)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 16)

    build_world()

    while not stop_event.is_set():
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                stop_event.set()
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                stop_event.set()

        draw_world(screen, font)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

###############################################################################
# Bootstrap
###############################################################################

async def run_agents(stop_event: threading.Event):
    traffic = TrafficControllerAgent(JID_TRAFFIC, PW_TRAFFIC, verify_security=False)
    car     = CarAgent(JID_CAR, PW_CAR, verify_security=False)
    emerg   = EmergencyAgent(JID_EMERG, PW_EMERG, verify_security=False)

    await traffic.start()
    await car.start()
    await emerg.start()
    print("Agentes iniciados.")

    try:
        while not stop_event.is_set():
            await asyncio.sleep(0.1)
    finally:
        print("A encerrar agentes...")
        await emerg.stop()
        await car.stop()
        await traffic.stop()

def main():
    stop_event = threading.Event()
    def spade_thread():
        asyncio.run(run_agents(stop_event))
    t = threading.Thread(target=spade_thread, daemon=True)
    t.start()
    run_pygame(stop_event)
    stop_event.set()
    t.join(timeout=2.0)

if __name__ == "__main__":
    main()
