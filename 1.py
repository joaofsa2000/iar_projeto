# city_three_agents_pretty_toggle_wait.py
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

JID_EMERG   = "emerg@localhost"    # viatura de emergência (cria no XMPP)
PW_EMERG    = "12345"

# tempos um pouco mais curtos
TIMINGS = dict(green=4.0, yellow=1.3)  # antes ~6.0/2.0

###############################################################################
# Modelo partilhado (render lê; agentes escrevem)
###############################################################################

@dataclass
class TrafficLightState:
    id: str
    pos: Tuple[int, int]       # centro (x, y) de referência no cruzamento
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
    wait_total: float = 0.0    # ⏱️ total parado (s)
    stopped_since: Optional[float] = None  # instante em que ficou parado

@dataclass
class SharedWorld:
    lock: threading.Lock = field(default_factory=threading.Lock)
    lights: Dict[str, TrafficLightState] = field(default_factory=dict)
    cars: Dict[str, CarState] = field(default_factory=dict)
    emergency_active: bool = False       # botão liga/desliga

WORLD = SharedWorld()

###############################################################################
# Geometria & Waypoints
###############################################################################

WIDTH, HEIGHT = 1100, 720
LANE = 26
ROAD_W = 2*LANE
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
        # Carro normal
        sp = (ROADS_X[0]-LANE, ROADS_Y[0]-2)
        tgt = (ROADS_X[1]+LANE, ROADS_Y[0]-2)
        d = normalize(tgt[0]-sp[0], tgt[1]-sp[1])
        WORLD.cars["C0"] = CarState(id="C0", pos=[float(sp[0]), float(sp[1])], dir=d,
                                    speed=90.0, target=tgt, kind="normal")
        # Emergência
        spE = (ROADS_X[0]-LANE, ROADS_Y[1]+LANE)
        tgtE = (ROADS_X[1]+LANE, ROADS_Y[1]+LANE)
        dE = normalize(tgtE[0]-spE[0], tgtE[1]-spE[1])
        WORLD.cars["E0"] = CarState(id="E0", pos=[float(spE[0]), float(spE[1])], dir=dE,
                                    speed=150.0, target=tgtE, kind="emergency")
        WORLD.emergency_active = False

###############################################################################
# Utilitários de “tempo parado”
###############################################################################

def update_wait_timer(car: CarState, is_stopped: bool):
    """Atualiza cronómetro de espera do carro com base no estado de paragem."""
    now = time.time()
    if is_stopped:
        if car.stopped_since is None:
            car.stopped_since = now  # começou a parar agora
    else:
        if car.stopped_since is not None:
            car.wait_total += (now - car.stopped_since)
            car.stopped_since = None

###############################################################################
# SEMÁFOROS — Agente controlador (ciclo curto)
###############################################################################

class TrafficControllerAgent(agent.Agent):
    class CycleBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            tG, tY = TIMINGS["green"], TIMINGS["yellow"]

            # NS verde
            with WORLD.lock:
                for l in WORLD.lights.values():
                    l.state = "VERDE" if l.orientation == "NS" else "VERMELHO"
            await asyncio.sleep(tG)

            # NS amarelo
            with WORLD.lock:
                for l in WORLD.lights.values():
                    if l.orientation == "NS" and l.state == "VERDE":
                        l.state = "AMARELO"
            await asyncio.sleep(tY)

            # EW verde
            with WORLD.lock:
                for l in WORLD.lights.values():
                    l.state = "VERDE" if l.orientation == "EW" else "VERMELHO"
            await asyncio.sleep(tG)

            # EW amarelo
            with WORLD.lock:
                for l in WORLD.lights.values():
                    if l.orientation == "EW" and l.state == "VERDE":
                        l.state = "AMARELO"
            await asyncio.sleep(tY)

    class RespondBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            # responde a pedidos de estado
            msg = await self.receive(timeout=0.1)
            if not msg: return
            parts = msg.body.split()
            if not parts: return
            if parts[0] == "STATE_REQ" and len(parts) >= 5:
                _, sx, sy, sdx, sdy = parts[:5]
                car_pos = (float(sx), float(sy))
                car_dir = normalize(float(sdx), float(sdy))
                best, best_d = None, 1e9
                with WORLD.lock:
                    for l in WORLD.lights.values():
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

    async def setup(self):
        print(f"[{self.name}] TrafficController iniciado.")
        self.add_behaviour(self.CycleBehaviour())
        self.add_behaviour(self.RespondBehaviour(), template.Template())

###############################################################################
# CARRO NORMAL — Agente (amarelo = abrandar; parado conta tempo)
###############################################################################

class CarAgent(agent.Agent):
    TRAFFIC_JID = JID_TRAFFIC

    class DriveBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            dt = 0.05
            with WORLD.lock:
                car = WORLD.cars.get("C0")
            if not car:
                await asyncio.sleep(dt); return

            speed_factor = 1.0
            state_seen = None
            near_light_pos = None

            with WORLD.lock:
                near = any(dist(car.pos, l.pos) < 120 for l in WORLD.lights.values())

            if near:
                req = message.Message(
                    to=self.agent.TRAFFIC_JID,
                    body=f"STATE_REQ {car.pos[0]} {car.pos[1]} {car.dir[0]} {car.dir[1]}",
                )
                await self.send(req)
                rep = await self.receive(timeout=0.05)
                if rep and rep.body.startswith("STATE_REP"):
                    _, lid, state, lx, ly = rep.body.split()[:5]
                    state_seen = state
                    if lid != "NONE":
                        near_light_pos = (float(lx), float(ly))
                        d_to = dist(car.pos, near_light_pos)
                        if state == "VERMELHO" and d_to < 70:
                            speed_factor = 0.0                     # PARAR
                        elif state == "AMARELO" and d_to < 80:
                            speed_factor = 0.35                    # ABRANDAR NO AMARELO
                        else:
                            speed_factor = 1.0
                else:
                    speed_factor = 0.6  # sem resposta, prudência

            # atualizar cronómetro de espera
            with WORLD.lock:
                update_wait_timer(car, is_stopped=(speed_factor == 0.0))

            # mover
            car.pos[0] += car.dir[0]*car.speed*dt*speed_factor
            car.pos[1] += car.dir[1]*car.speed*dt*speed_factor

            # waypoint loop
            if dist(car.pos, car.target) < 8:
                car.target = next_waypoint_loop(car.target)
                car.dir = normalize(car.target[0]-car.pos[0], car.target[1]-car.pos[1])

            await asyncio.sleep(dt)

    async def setup(self):
        print(f"[{self.name}] CarAgent iniciado.")
        self.add_behaviour(self.DriveBehaviour())

###############################################################################
# EMERGÊNCIA — Agente (toggle ON/OFF; luz só com botão ON)
###############################################################################

class EmergencyAgent(agent.Agent):
    TRAFFIC_JID = JID_TRAFFIC

    class DriveBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            dt = 0.05
            with WORLD.lock:
                car = WORLD.cars.get("E0")
                emergency_on = WORLD.emergency_active
            if not car:
                await asyncio.sleep(dt); return

            if emergency_on:
                # IGNORA semáforos + anda mais depressa
                speed_factor = 1.25
                # não conta tempo parado (não para)
                with WORLD.lock:
                    update_wait_timer(car, is_stopped=False)
            else:
                # MODO NORMAL: igual ao CarAgent (amarelo abranda)
                speed_factor = 1.0
                with WORLD.lock:
                    near = any(dist(car.pos, l.pos) < 120 for l in WORLD.lights.values())
                if near:
                    req = message.Message(
                        to=self.agent.TRAFFIC_JID,
                        body=f"STATE_REQ {car.pos[0]} {car.pos[1]} {car.dir[0]} {car.dir[1]}",
                    )
                    await self.send(req)
                    rep = await self.receive(timeout=0.05)
                    if rep and rep.body.startswith("STATE_REP"):
                        _, lid, state, lx, ly = rep.body.split()[:5]
                        if lid != "NONE":
                            d_to = dist(car.pos, (float(lx), float(ly)))
                            if state == "VERMELHO" and d_to < 70:
                                speed_factor = 0.0
                            elif state == "AMARELO" and d_to < 80:
                                speed_factor = 0.35
                            else:
                                speed_factor = 1.0
                    else:
                        speed_factor = 0.6
                with WORLD.lock:
                    update_wait_timer(car, is_stopped=(speed_factor == 0.0))

            # mover
            car.pos[0] += car.dir[0]*car.speed*dt*speed_factor
            car.pos[1] += car.dir[1]*car.speed*dt*speed_factor

            # waypoint
            if dist(car.pos, car.target) < 8:
                car.target = next_waypoint_loop(car.target)
                car.dir = normalize(car.target[0]-car.pos[0], car.target[1]-car.pos[1])

            await asyncio.sleep(dt)

    async def setup(self):
        print(f"[{self.name}] EmergencyAgent iniciado (toggle ON/OFF).")
        self.add_behaviour(self.DriveBehaviour())

###############################################################################
# GRÁFICOS — helpers
###############################################################################

COL_BG        = (28, 30, 34)
COL_SIDEWALK  = (65, 68, 72)
COL_ROAD      = (54, 56, 60)
COL_LINE      = (210, 210, 210)
COL_DASH      = (240, 240, 140)

def aa_round_rect(surface, rect, color, radius):
    pygame.draw.rect(surface, color, rect, border_radius=radius)

def draw_sidewalks(screen):
    sw = 10
    for rx in ROADS_X:
        pygame.draw.rect(screen, COL_SIDEWALK, pygame.Rect(rx-ROAD_W//2 - sw, 0, sw, HEIGHT))
        pygame.draw.rect(screen, COL_SIDEWALK, pygame.Rect(rx+ROAD_W//2, 0, sw, HEIGHT))
    for ry in ROADS_Y:
        pygame.draw.rect(screen, COL_SIDEWALK, pygame.Rect(0, ry-ROAD_W//2 - sw, WIDTH, sw))
        pygame.draw.rect(screen, COL_SIDEWALK, pygame.Rect(0, ry+ROAD_W//2, WIDTH, sw))

def draw_roads(screen):
    for rx in ROADS_X:
        pygame.draw.rect(screen, COL_ROAD, pygame.Rect(rx-ROAD_W//2, 0, ROAD_W, HEIGHT))
    for ry in ROADS_Y:
        pygame.draw.rect(screen, COL_ROAD, pygame.Rect(0, ry-ROAD_W//2, WIDTH, ROAD_W))
    dash_len = 22
    gap = 18
    for rx in ROADS_X:
        x = rx
        y = 0
        while y < HEIGHT:
            pygame.draw.line(screen, COL_DASH, (x, y), (x, min(y+dash_len, HEIGHT)), 3)
            y += dash_len + gap
    for ry in ROADS_Y:
        y = ry
        x = 0
        while x < WIDTH:
            pygame.draw.line(screen, COL_DASH, (x, y), (min(x+dash_len, WIDTH), y), 3)
            x += dash_len + gap
    edge_w = 2
    for rx in ROADS_X:
        pygame.draw.line(screen, COL_LINE, (rx-ROAD_W//2, 0), (rx-ROAD_W//2, HEIGHT), edge_w)
        pygame.draw.line(screen, COL_LINE, (rx+ROAD_W//2, 0), (rx+ROAD_W//2, HEIGHT), edge_w)
    for ry in ROADS_Y:
        pygame.draw.line(screen, COL_LINE, (0, ry-ROAD_W//2), (WIDTH, ry-ROAD_W//2), edge_w)
        pygame.draw.line(screen, COL_LINE, (0, ry+ROAD_W//2), (WIDTH, ry+ROAD_W//2), edge_w)

def draw_light(screen, l: TrafficLightState):
    pole_color = (50, 50, 50)
    bx, by = l.pos
    if l.orientation == "NS":
        bx += 14; by -= 6
    else:
        bx -= 6; by += 14
    pygame.draw.rect(screen, pole_color, pygame.Rect(bx-2, by-22, 4, 28))
    box = pygame.Rect(bx-10, by-38, 20, 36)
    pygame.draw.rect(screen, (20, 20, 22), box, border_radius=4)
    pygame.draw.rect(screen, (90, 90, 95), box, width=2, border_radius=4)
    slots = [(bx, by-30), (bx, by-20), (bx, by-10)]
    state_on = dict(VERMELHO=0, AMARELO=1, VERDE=2).get(l.state, -1)
    colors = [(220, 80, 80), (240, 210, 90), (90, 210, 110)]
    for i, center in enumerate(slots):
        c = colors[i]; on = (i == state_on)
        pygame.draw.circle(screen, c if on else (60, 60, 60), center, 4)
        if on:
            glow = pygame.Surface((40, 40), pygame.SRCALPHA)
            gc = (*c, 80)
            pygame.draw.circle(glow, gc, (20, 20), 12)
            screen.blit(glow, (center[0]-20, center[1]-20), special_flags=pygame.BLEND_PREMULTIPLIED)

def make_car_surface(color_body=(160,200,255), emergency=False):
    w, h = (38, 20) if emergency else (34, 18)
    surf = pygame.Surface((w+12, h+12), pygame.SRCALPHA)
    shadow = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0,0,0,90), pygame.Rect(0,0,w,h))
    surf.blit(shadow, (6, 8))
    body_rect = pygame.Rect(6, 6, w, h)
    aa_round_rect(surf, body_rect, color_body, 6)
    rw = 6; rh = 2; wheel_color = (30,30,30)
    for dx in [10, w-6]:
        pygame.draw.rect(surf, wheel_color, pygame.Rect(6+dx-3, 6+2, rw, rh), border_radius=2)
        pygame.draw.rect(surf, wheel_color, pygame.Rect(6+dx-3, 6+h-4, rw, rh), border_radius=2)
    pygame.draw.rect(surf, (220, 220, 235), pygame.Rect(6+w-10, 6+3, 8, h-6), border_radius=2)
    if emergency:
        pygame.draw.rect(surf, (230,230,255), pygame.Rect(6+w//2-5, 6+2, 10, 4), border_radius=2)
    return surf

CAR_SURF = None
EMERG_SURF = None

def draw_car(screen, c: CarState):
    global CAR_SURF, EMERG_SURF
    if CAR_SURF is None: CAR_SURF = make_car_surface()
    if EMERG_SURF is None: EMERG_SURF = make_car_surface(color_body=(255,160,60), emergency=True)
    base = EMERG_SURF if c.kind=="emergency" else CAR_SURF
    angle = math.degrees(math.atan2(c.dir[1], c.dir[0]))
    rotated = pygame.transform.rotate(base, -angle)
    rect = rotated.get_rect(center=(int(c.pos[0]), int(c.pos[1])))
    screen.blit(rotated, rect.topleft)
    # Giroflex só quando emergência está ON
    if c.kind == "emergency":
        with WORLD.lock:
            emer_on = WORLD.emergency_active
        if emer_on:
            t = pygame.time.get_ticks()
            if (t//160) % 2 == 0:
                flash = pygame.Surface((18, 10), pygame.SRCALPHA)
                pygame.draw.ellipse(flash, (255,255,255,120), pygame.Rect(0,0,18,10))
                screen.blit(flash, (rect.centerx-9, rect.top-4))

def draw_hud(screen, font_small):
    strip = pygame.Surface((WIDTH, 52), pygame.SRCALPHA)
    strip.fill((10, 10, 12, 210))
    screen.blit(strip, (0, 0))
    with WORLD.lock:
        lights = list(WORLD.lights.values())
        cars = WORLD.cars
        emer = WORLD.emergency_active
        c0 = cars.get("C0")
        e0 = cars.get("E0")
        wait_c0 = (c0.wait_total + (time.time()-c0.stopped_since if c0 and c0.stopped_since else 0.0)) if c0 else 0.0
        wait_e0 = (e0.wait_total + (time.time()-e0.stopped_since if e0 and e0.stopped_since else 0.0)) if e0 else 0.0
    ns = sum(1 for l in lights if l.orientation=="NS" and l.state=="VERDE")
    ew = sum(1 for l in lights if l.orientation=="EW" and l.state=="VERDE")
    status = "ON" if emer else "OFF"
    txt1 = f"Semáforos NS verdes: {ns} | EW verdes: {ew} | Emergência: {status}"
    txt2 = f"Tempo parado C0: {wait_c0:4.1f}s   |   E0: {wait_e0:4.1f}s"
    screen.blit(font_small.render(txt1, True, (235,235,235)), (12, 8))
    screen.blit(font_small.render(txt2, True, (210,210,210)), (12, 28))

# Botão toggle
BTN_RECT = pygame.Rect(WIDTH-210, 8, 190, 24)

def draw_button(screen, font_small):
    with WORLD.lock:
        on = WORLD.emergency_active
    bg = (60, 140, 90) if on else (120, 120, 120)
    pygame.draw.rect(screen, bg, BTN_RECT, border_radius=8)
    pygame.draw.rect(screen, (20,20,20), BTN_RECT, width=2, border_radius=8)
    label = "Emergência: ON" if on else "Emergência: OFF"
    txt = font_small.render(label, True, (255,255,255))
    screen.blit(txt, (BTN_RECT.x+12, BTN_RECT.y+4))

###############################################################################
# RENDER LOOP
###############################################################################

def draw_world(screen, font_small):
    screen.fill((28, 30, 34))
    # passeios
    sw = 10
    for rx in ROADS_X:
        pygame.draw.rect(screen, (65,68,72), pygame.Rect(rx-ROAD_W//2 - sw, 0, sw, HEIGHT))
        pygame.draw.rect(screen, (65,68,72), pygame.Rect(rx+ROAD_W//2, 0, sw, HEIGHT))
    for ry in ROADS_Y:
        pygame.draw.rect(screen, (65,68,72), pygame.Rect(0, ry-ROAD_W//2 - sw, WIDTH, sw))
        pygame.draw.rect(screen, (65,68,72), pygame.Rect(0, ry+ROAD_W//2, WIDTH, sw))
    # vias
    for rx in ROADS_X:
        pygame.draw.rect(screen, (54,56,60), pygame.Rect(rx-ROAD_W//2, 0, ROAD_W, HEIGHT))
    for ry in ROADS_Y:
        pygame.draw.rect(screen, (54,56,60), pygame.Rect(0, ry-ROAD_W//2, WIDTH, ROAD_W))
    # tracejadas
    dash_len = 22; gap = 18
    for rx in ROADS_X:
        y = 0
        while y < HEIGHT:
            pygame.draw.line(screen, (240,240,140), (rx, y), (rx, min(y+dash_len, HEIGHT)), 3)
            y += dash_len + gap
    for ry in ROADS_Y:
        x = 0
        while x < WIDTH:
            pygame.draw.line(screen, (240,240,140), (x, ry), (min(x+dash_len, WIDTH), ry), 3)
            x += dash_len + gap
    # bordas
    edge_w = 2
    for rx in ROADS_X:
        pygame.draw.line(screen, (210,210,210), (rx-ROAD_W//2, 0), (rx-ROAD_W//2, HEIGHT), edge_w)
        pygame.draw.line(screen, (210,210,210), (rx+ROAD_W//2, 0), (rx+ROAD_W//2, HEIGHT), edge_w)
    for ry in ROADS_Y:
        pygame.draw.line(screen, (210,210,210), (0, ry-ROAD_W//2), (WIDTH, ry-ROAD_W//2), edge_w)
        pygame.draw.line(screen, (210,210,210), (0, ry+ROAD_W//2), (WIDTH, ry+ROAD_W//2), edge_w)

    with WORLD.lock:
        lights = list(WORLD.lights.values())
        cars = list(WORLD.cars.values())

    # semáforos
    for l in lights:
        # desenha
        pole_color = (50, 50, 50)
        bx, by = l.pos
        if l.orientation == "NS":
            bx += 14; by -= 6
        else:
            bx -= 6; by += 14
        pygame.draw.rect(screen, pole_color, pygame.Rect(bx-2, by-22, 4, 28))
        box = pygame.Rect(bx-10, by-38, 20, 36)
        pygame.draw.rect(screen, (20, 20, 22), box, border_radius=4)
        pygame.draw.rect(screen, (90, 90, 95), box, width=2, border_radius=4)
        slots = [(bx, by-30), (bx, by-20), (bx, by-10)]
        state_on = dict(VERMELHO=0, AMARELO=1, VERDE=2).get(l.state, -1)
        colors = [(220, 80, 80), (240, 210, 90), (90, 210, 110)]
        for i, center in enumerate(slots):
            c = colors[i]; on = (i == state_on)
            pygame.draw.circle(screen, c if on else (60, 60, 60), center, 4)
            if on:
                glow = pygame.Surface((40, 40), pygame.SRCALPHA)
                gc = (*c, 80)
                pygame.draw.circle(glow, gc, (20, 20), 12)
                screen.blit(glow, (center[0]-20, center[1]-20), special_flags=pygame.BLEND_PREMULTIPLIED)

    for c in cars:
        # sprites
        def get_surf(kind):
            w, h = (38, 20) if kind=="emergency" else (34, 18)
            surf = pygame.Surface((w+12, h+12), pygame.SRCALPHA)
            shadow = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0,0,0,90), pygame.Rect(0,0,w,h))
            surf.blit(shadow, (6, 8))
            body_rect = pygame.Rect(6, 6, w, h)
            color_body = (255,160,60) if kind=="emergency" else (160,200,255)
            pygame.draw.rect(surf, color_body, body_rect, border_radius=6)
            rw = 6; rh = 2; wheel_color = (30,30,30)
            for dx in [10, w-6]:
                pygame.draw.rect(surf, wheel_color, pygame.Rect(6+dx-3, 6+2, rw, rh), border_radius=2)
                pygame.draw.rect(surf, wheel_color, pygame.Rect(6+dx-3, 6+h-4, rw, rh), border_radius=2)
            pygame.draw.rect(surf, (220, 220, 235), pygame.Rect(6+w-10, 6+3, 8, h-6), border_radius=2)
            if kind=="emergency":
                pygame.draw.rect(surf, (230,230,255), pygame.Rect(6+w//2-5, 6+2, 10, 4), border_radius=2)
            return surf

        base = get_surf(c.kind)
        angle = math.degrees(math.atan2(c.dir[1], c.dir[0]))
        rotated = pygame.transform.rotate(base, -angle)
        rect = rotated.get_rect(center=(int(c.pos[0]), int(c.pos[1])))
        screen.blit(rotated, rect.topleft)
        if c.kind == "emergency":
            with WORLD.lock:
                emer_on = WORLD.emergency_active
            if emer_on:
                t = pygame.time.get_ticks()
                if (t//160) % 2 == 0:
                    flash = pygame.Surface((18, 10), pygame.SRCALPHA)
                    pygame.draw.ellipse(flash, (255,255,255,120), pygame.Rect(0,0,18,10))
                    screen.blit(flash, (rect.centerx-9, rect.top-4))

    font_small = pygame.font.SysFont("Inter,Arial,Helvetica", 16)
    # HUD + botão
    strip = pygame.Surface((WIDTH, 52), pygame.SRCALPHA); strip.fill((10,10,12,210)); screen.blit(strip, (0,0))
    with WORLD.lock:
        lights = list(WORLD.lights.values()); cars_map = WORLD.cars; emer = WORLD.emergency_active
        c0 = cars_map.get("C0"); e0 = cars_map.get("E0")
        wait_c0 = (c0.wait_total + (time.time()-c0.stopped_since if c0 and c0.stopped_since else 0.0)) if c0 else 0.0
        wait_e0 = (e0.wait_total + (time.time()-e0.stopped_since if e0 and e0.stopped_since else 0.0)) if e0 else 0.0
    ns = sum(1 for l in lights if l.orientation=="NS" and l.state=="VERDE")
    ew = sum(1 for l in lights if l.orientation=="EW" and l.state=="VERDE")
    status = "ON" if emer else "OFF"
    screen.blit(font_small.render(f"Semáforos NS verdes: {ns} | EW verdes: {ew} | Emergência: {status}", True, (235,235,235)), (12, 8))
    screen.blit(font_small.render(f"Tempo parado C0: {wait_c0:4.1f}s   |   E0: {wait_e0:4.1f}s", True, (210,210,210)), (12, 28))

    # botão
    bg = (60,140,90) if emer else (120,120,120)
    BTN_RECT = pygame.Rect(WIDTH-210, 8, 190, 24)
    pygame.draw.rect(screen, bg, BTN_RECT, border_radius=8)
    pygame.draw.rect(screen, (20,20,20), BTN_RECT, width=2, border_radius=8)
    label = "Emergência: ON" if emer else "Emergência: OFF"
    screen.blit(font_small.render(label, True, (255,255,255)), (BTN_RECT.x+12, BTN_RECT.y+4))
    return BTN_RECT

def run_pygame(stop_event: threading.Event):
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Cidade Multi-Agente — Espera, Amarelo e Emergência ON/OFF")
    clock = pygame.time.Clock()

    build_world()

    btn_rect = pygame.Rect(WIDTH-210, 8, 190, 24)

    while not stop_event.is_set():
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                stop_event.set()
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                stop_event.set()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if btn_rect.collidepoint(e.pos):
                    with WORLD.lock:
                        WORLD.emergency_active = not WORLD.emergency_active

        btn_rect = draw_world(screen, pygame.font.SysFont("Inter,Arial,Helvetica", 16))
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

###############################################################################
# BOOTSTRAP — SPADE numa thread separada
###############################################################################

class CarAgentRunner(agent.Agent): pass  # (placeholders só para manter tipagem do plugin)

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
