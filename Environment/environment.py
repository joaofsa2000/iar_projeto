import csv
import random
import os
import ctypes
import pygame
from datetime import datetime, timedelta
from collections import defaultdict

from Map.Car import Car
from Map.Crash import Crash
from Map.EmergencyCar import EmergencyCar
from Data.MetricsManager import get_metrics_manager

# Update Car class time speed whenever environment changes it
def _sync_car_time_speed(time_speed, is_paused):
    """Sync the Car class time speed with environment."""
    Car.set_time_speed(time_speed, is_paused)

from Map.Intersection import Intersection
from Map.TrafficLight import TrafficLight

CRASH_POSITIONS = {
    "top_left": [("l", (153, 132)), ("r", (363, 198)), ("b", (225, 269)), ("t", (293, 59))],
    "top_mid": [("t", (651, 59)), ("l", (512, 131)), ("r", (722, 198)), ("b", (584, 268))],
    "top_right": [("b", (948, 269)), ("r", (1088, 197)), ("t", (1016, 59)), ("l", (876, 131))],
    "bottom_left": [("t", (291, 406)), ("r", (364, 546)), ("b", (225, 618)), ("l", (155, 482))],
    "bottom_mid": [("b", (583, 618)), ("r", (722, 547)), ("t", (649, 409)), ("l",(512, 481))],
    "bottom_right": [("l", (876, 480)), ("t", (1015, 409)), ("r", (1088, 547)), ("b", (948, 620))]
}

# Intersection IDs for metrics tracking
INTERSECTION_IDS = ["top_left", "top_mid", "top_right", "bottom_left", "bottom_mid", "bottom_right"]

# Disruption types (Portuguese labels)
class DisruptionType:
    NONE = "none"
    ACCIDENT = "acidente"
    CONSTRUCTION = "obras"
    BAD_WEATHER = "mau_tempo"
    ROAD_CLOSURE = "estrada_cortada"
    SPECIAL_EVENT = "evento_especial"


# Portuguese labels for disruption types
DISRUPTION_LABELS_PT = {
    DisruptionType.NONE: "Nenhuma",
    DisruptionType.ACCIDENT: "Acidente",
    DisruptionType.CONSTRUCTION: "Obras",
    DisruptionType.BAD_WEATHER: "Mau Tempo",
    DisruptionType.ROAD_CLOSURE: "Estrada Cortada",
    DisruptionType.SPECIAL_EVENT: "Evento Especial",
}

# Portuguese intersection names
INTERSECTION_NAMES_PT = {
    "top_left": "Superior Esquerdo",
    "top_mid": "Superior Central",
    "top_right": "Superior Direito",
    "bottom_left": "Inferior Esquerdo",
    "bottom_mid": "Inferior Central",
    "bottom_right": "Inferior Direito",
}


# Traffic density profiles for different times of day
# Values represent relative traffic volume (0.0 to 1.0)
TRAFFIC_PATTERNS = {
    0: 0.1,   # 00:00 - Very low (night)
    1: 0.05,  # 01:00 - Minimal
    2: 0.05,  # 02:00 - Minimal
    3: 0.05,  # 03:00 - Minimal
    4: 0.1,   # 04:00 - Starting to increase
    5: 0.2,   # 05:00 - Early commuters
    6: 0.4,   # 06:00 - Building up
    7: 0.7,   # 07:00 - Rush hour begins
    8: 1.0,   # 08:00 - Peak morning rush
    9: 0.8,   # 09:00 - Rush hour ending
    10: 0.5,  # 10:00 - Mid-morning
    11: 0.5,  # 11:00 - Mid-morning
    12: 0.6,  # 12:00 - Lunch time
    13: 0.6,  # 13:00 - Lunch time
    14: 0.5,  # 14:00 - Afternoon
    15: 0.5,  # 15:00 - Afternoon
    16: 0.6,  # 16:00 - Building up
    17: 0.9,  # 17:00 - Evening rush begins
    18: 1.0,  # 18:00 - Peak evening rush
    19: 0.7,  # 19:00 - Rush hour ending
    20: 0.4,  # 20:00 - Evening
    21: 0.3,  # 21:00 - Evening
    22: 0.2,  # 22:00 - Night
    23: 0.15, # 23:00 - Night
}


class Environment:
    # Base resolution (original design resolution)
    BASE_WIDTH = 1280
    BASE_HEIGHT = 720
    
    def __init__(self, fullscreen=True, display_index=0):
        """
        Initialize the environment.
        
        Args:
            fullscreen: If True, uses borderless fullscreen mode
            display_index: Index of the display/monitor to use (0 = primary, 1 = secondary, etc.)
        """
        # Initialize pygame
        pygame.init()
        pygame.font.init()
        
        # ============================================================
        # MULTI-MONITOR SUPPORT
        # ============================================================
        self.display_index = display_index
        self.available_displays = self._get_available_displays()
        self.current_display = self._get_display_info(display_index)
        
        print(f"[DISPLAY] Monitores disponíveis: {len(self.available_displays)}")
        for i, disp in enumerate(self.available_displays):
            marker = " <-- SELECIONADO" if i == display_index else ""
            print(f"[DISPLAY]   Monitor {i}: {disp['width']}x{disp['height']} em ({disp['x']}, {disp['y']}){marker}")
        
        # ============================================================
        # DISPLAY SETUP - BORDERLESS WINDOWED (recommended for Windows 11)
        # ============================================================
        self.fullscreen = fullscreen
        
        if fullscreen:
            # Position window on selected display
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{self.current_display['x']},{self.current_display['y']}"
            
            self.screen_width = self.current_display['width']
            self.screen_height = self.current_display['height']
            
            # Use NOFRAME (borderless window) instead of FULLSCREEN
            # This works better with Windows 11's compositor (DWM)
            self.screen = pygame.display.set_mode(
                (self.screen_width, self.screen_height),
                pygame.NOFRAME | pygame.DOUBLEBUF | pygame.HWSURFACE,
                vsync=1  # Enable vsync
            )
        else:
            # Windowed mode - center on selected display
            window_x = self.current_display['x'] + (self.current_display['width'] - self.BASE_WIDTH) // 2
            window_y = self.current_display['y'] + (self.current_display['height'] - self.BASE_HEIGHT) // 2
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{window_x},{window_y}"
            
            self.screen_width = self.BASE_WIDTH
            self.screen_height = self.BASE_HEIGHT
            self.screen = pygame.display.set_mode(
                (self.screen_width, self.screen_height),
                pygame.DOUBLEBUF | pygame.RESIZABLE,
                vsync=1
            )
        
        # Calculate scaling to maintain aspect ratio
        self._calculate_scaling()
        
        # Create the game surface at base resolution (all rendering happens here)
        self.game_surface = pygame.Surface((self.BASE_WIDTH, self.BASE_HEIGHT))
        
        pygame.display.set_caption("Sistema de Gestão de Tráfego - Prima F1 para Ajuda")
        
        # Load and prepare background
        self.bg_surf = pygame.image.load('Map/Resources/fundo.png').convert()
        
        # Clock for timing
        self.clock = pygame.time.Clock()
        self.target_fps = 0  # 0 means use vsync (no artificial limit)
        
        # ============================================================
        # FONTS (scaled for display)
        # ============================================================
        # Base font sizes (for 720p)
        self.font_large = pygame.font.SysFont('Arial', 24, bold=True)
        self.font_medium = pygame.font.SysFont('Arial', 18)
        self.font_small = pygame.font.SysFont('Arial', 14)
        self.font_time = pygame.font.SysFont('Arial', 32, bold=True)

        # cria conjunto de cruzamentos no mapa
        self.intersections = pygame.sprite.Group()
        self.intersections.add(Intersection(193, 450))  # cruzamento inferior esquerdo
        self.intersections.add(Intersection(552, 450))  # cruzamento inferior central
        self.intersections.add(Intersection(917, 450))  # cruzamento inferior direito
        self.intersections.add(Intersection(193, 100))  # cruzamento superior esquerdo
        self.intersections.add(Intersection(552, 100))  # cruzamento superior central
        self.intersections.add(Intersection(917, 100))  # cruzamento superior direito

        # estruturas de dados para gestão de veículos
        self.cars = []
        self.emergency_cars = []
        self.emergency_cars_awaiting_time = {}
        self.car_positions = {}
        self.cars_stopped_at_tl = {}

        # estruturas de dados para gestão de semáforos
        self.traffic_lights = pygame.sprite.Group()
        self.traffic_lights_objects = {}
        self.traffic_lights_agents_tl = {}
        self.traffic_lights_status = {}

        self.cars_stopped_times = []

        self.map_crash = False
        self.crash_position = (0, 0)
        self.crash_location = ""
        
        # ============================================================
        # SIMULAÇÃO TEMPORAL 24 HORAS
        # ============================================================
        self.simulation_time = datetime(2024, 1, 1, 7, 0, 0)  # Início às 7:00
        self.time_speed_options = [0, 1, 2, 5, 10, 30, 60, 120, 300, 600]  # Multiplicadores de velocidade
        self.time_speed_index = 3  # Predefinido: 5x velocidade
        self.time_speed = self.time_speed_options[self.time_speed_index]
        self.last_time_update = datetime.now()
        self.is_paused = False
        
        # Traffic density based on time
        self.current_traffic_density = 0.5
        self.car_spawn_probability = 0.04  # Base probability per frame (increased)
        
        # Day/night visual effects
        self.day_night_overlay_alpha = 0
        
        # ============================================================
        # GESTÃO DE PERTURBAÇÕES
        # ============================================================
        self.show_help = False  # F1 alterna sobreposição de ajuda
        self.active_disruptions = {}  # {intersection_id: DisruptionType}
        self.disruption_start_times = {}  # {intersection_id: datetime}
        self.global_disruption = DisruptionType.NONE  # Perturbação global (ex: tempo)
        self.speed_modifier = 1.0  # Redução de velocidade por perturbações (1.0 = normal)
        
        # Disruption visual indicators
        self.disruption_colors = {
            DisruptionType.NONE: (0, 255, 0),        # Verde
            DisruptionType.ACCIDENT: (255, 0, 0),    # Vermelho
            DisruptionType.CONSTRUCTION: (255, 165, 0),  # Laranja
            DisruptionType.BAD_WEATHER: (100, 100, 255),  # Azul claro
            DisruptionType.ROAD_CLOSURE: (128, 0, 128),   # Roxo
            DisruptionType.SPECIAL_EVENT: (255, 255, 0),  # Amarelo
        }
        
        # Selected intersection for disruption placement
        self.selected_intersection_index = 0
        
        # ============================================================
        # MÉTRICAS DE DESEMPENHO
        # ============================================================
        
        # Veículos que passaram por cruzamento
        self.vehicles_passed_per_intersection = defaultdict(int)
        
        # Níveis de congestionamento por cruzamento
        self.congestion_levels = defaultdict(float)
        
        # Histórico de posições para cálculo de velocidade
        self.car_position_history = defaultdict(list)  # {car_id: [(x, y, timestamp), ...]}
        self.car_speeds = defaultdict(float)  # {car_id: current_speed}
        
        # Intersection boundaries for tracking vehicles passing through
        self.intersection_bounds = {
            "top_left": (193, 100, 160, 160),      # (x, y, width, height)
            "top_mid": (552, 100, 160, 160),
            "top_right": (917, 100, 160, 160),
            "bottom_left": (193, 450, 160, 160),
            "bottom_mid": (552, 450, 160, 160),
            "bottom_right": (917, 450, 160, 160),
        }
        
        # Intersection center positions for UI
        self.intersection_centers = {
            "top_left": (268, 180),
            "top_mid": (627, 180),
            "top_right": (992, 180),
            "bottom_left": (268, 530),
            "bottom_mid": (627, 530),
            "bottom_right": (992, 530),
        }
        
        # Track which cars have passed each intersection (to avoid double counting)
        self.cars_passed_intersections = defaultdict(set)  # {intersection_id: {car_ids}}
        
        # Simulation start time (real world)
        self.simulation_start_time = datetime.now()
        
        # FPS display
        self.show_fps = True
        
        # ============================================================
        # METRICS MANAGER - Save data for analysis and ML training
        # ============================================================
        self.metrics_manager = get_metrics_manager()
        self.last_metrics_save = datetime.now()
        self.metrics_save_interval = 5  # Save metrics every 5 seconds of real time
        self.last_snapshot_time = datetime.now()

    def _get_available_displays(self):
        """Get information about all available displays/monitors."""
        displays = []
        
        try:
            # Try to use Windows API for accurate multi-monitor info
            if os.name == 'nt':
                user32 = ctypes.windll.user32
                
                # Callback function to enumerate monitors
                MONITOR_ENUM_PROC = ctypes.WINFUNCTYPE(
                    ctypes.c_int,
                    ctypes.c_ulong,
                    ctypes.c_ulong,
                    ctypes.POINTER(ctypes.c_long * 4),
                    ctypes.c_double
                )
                
                monitors = []
                
                def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
                    rect = lprcMonitor.contents
                    monitors.append({
                        'x': rect[0],
                        'y': rect[1],
                        'width': rect[2] - rect[0],
                        'height': rect[3] - rect[1]
                    })
                    return 1
                
                user32.EnumDisplayMonitors(None, None, MONITOR_ENUM_PROC(callback), 0)
                
                # Sort by x position (left to right)
                monitors.sort(key=lambda m: (m['x'], m['y']))
                displays = monitors
        except Exception as e:
            print(f"[DISPLAY] Erro ao enumerar monitores: {e}")
        
        # Fallback: use pygame's display info
        if not displays:
            try:
                num_displays = pygame.display.get_num_displays()
                for i in range(num_displays):
                    display_info = pygame.display.Info()
                    displays.append({
                        'x': 0 if i == 0 else displays[-1]['x'] + displays[-1]['width'],
                        'y': 0,
                        'width': display_info.current_w,
                        'height': display_info.current_h
                    })
            except:
                # Final fallback
                display_info = pygame.display.Info()
                displays.append({
                    'x': 0,
                    'y': 0,
                    'width': display_info.current_w,
                    'height': display_info.current_h
                })
        
        return displays
    
    def _get_display_info(self, index):
        """Get information about a specific display."""
        if index < 0 or index >= len(self.available_displays):
            print(f"[DISPLAY] Monitor {index} não existe, usando monitor 0")
            index = 0
        return self.available_displays[index]
    
    def switch_display(self, display_index):
        """Switch the window to a different display."""
        if display_index < 0 or display_index >= len(self.available_displays):
            print(f"[DISPLAY] Monitor {display_index} não existe")
            return
        
        self.display_index = display_index
        self.current_display = self._get_display_info(display_index)
        
        if self.fullscreen:
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{self.current_display['x']},{self.current_display['y']}"
            self.screen_width = self.current_display['width']
            self.screen_height = self.current_display['height']
            
            # Recreate the display
            self.screen = pygame.display.set_mode(
                (self.screen_width, self.screen_height),
                pygame.NOFRAME | pygame.DOUBLEBUF | pygame.HWSURFACE,
                vsync=1
            )
        else:
            window_x = self.current_display['x'] + (self.current_display['width'] - self.BASE_WIDTH) // 2
            window_y = self.current_display['y'] + (self.current_display['height'] - self.BASE_HEIGHT) // 2
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{window_x},{window_y}"
            
            self.screen = pygame.display.set_mode(
                (self.screen_width, self.screen_height),
                pygame.DOUBLEBUF | pygame.RESIZABLE,
                vsync=1
            )
        
        self._calculate_scaling()
        print(f"[DISPLAY] Mudado para monitor {display_index}")

    def _calculate_scaling(self):
        """Calculate the scale factor to fit the base resolution into the screen."""
        # Calculate scale to fit while maintaining aspect ratio
        scale_x = self.screen_width / self.BASE_WIDTH
        scale_y = self.screen_height / self.BASE_HEIGHT
        
        # Use the smaller scale to ensure everything fits
        self.scale = min(scale_x, scale_y)
        
        # Calculate the scaled dimensions
        self.scaled_width = int(self.BASE_WIDTH * self.scale)
        self.scaled_height = int(self.BASE_HEIGHT * self.scale)
        
        # Calculate offset to center the game on screen
        self.offset_x = (self.screen_width - self.scaled_width) // 2
        self.offset_y = (self.screen_height - self.scaled_height) // 2
        
        print(f"[DISPLAY] Ecrã: {self.screen_width}x{self.screen_height}")
        print(f"[DISPLAY] Base: {self.BASE_WIDTH}x{self.BASE_HEIGHT}")
        print(f"[DISPLAY] Escala: {self.scale:.2f}x")
        print(f"[DISPLAY] Área de jogo: {self.scaled_width}x{self.scaled_height}")
        print(f"[DISPLAY] Offset: ({self.offset_x}, {self.offset_y})")

    def toggle_fullscreen(self):
        """Toggle between borderless fullscreen and windowed mode."""
        self.fullscreen = not self.fullscreen
        
        if self.fullscreen:
            # Borderless windowed (recommended for Windows 11)
            display_info = pygame.display.Info()
            self.screen_width = display_info.current_w
            self.screen_height = display_info.current_h
            self.screen = pygame.display.set_mode(
                (self.screen_width, self.screen_height),
                pygame.NOFRAME | pygame.DOUBLEBUF | pygame.HWSURFACE,
                vsync=1
            )
        else:
            # Windowed mode with resize capability
            self.screen_width = self.BASE_WIDTH
            self.screen_height = self.BASE_HEIGHT
            self.screen = pygame.display.set_mode(
                (self.screen_width, self.screen_height),
                pygame.DOUBLEBUF | pygame.RESIZABLE,
                vsync=1
            )
        
        self._calculate_scaling()
        print(f"[DISPLAY] Modo: {'Ecrã Inteiro (Borderless)' if self.fullscreen else 'Janela'}")

    def get_game_surface(self):
        """Get the game surface for rendering (at base resolution)."""
        return self.game_surface

    # ============================================================
    # MÉTODOS DE SIMULAÇÃO TEMPORAL
    # ============================================================
    
    def update_simulation_time(self):
        """Update the simulation clock based on time speed."""
        # Sync car time speed
        _sync_car_time_speed(self.time_speed, self.is_paused)
        
        if self.is_paused or self.time_speed == 0:
            self.last_time_update = datetime.now()
            return
        
        now = datetime.now()
        real_elapsed = (now - self.last_time_update).total_seconds()
        self.last_time_update = now
        
        # Calculate simulation time elapsed
        sim_elapsed = real_elapsed * self.time_speed
        self.simulation_time += timedelta(seconds=sim_elapsed)
        
        # Update traffic density based on hour
        self._update_traffic_density()
        
        # Update day/night visual effect
        self._update_day_night_effect()
    
    def _update_traffic_density(self):
        """Update traffic density based on current simulation hour."""
        hour = self.simulation_time.hour
        self.current_traffic_density = TRAFFIC_PATTERNS.get(hour, 0.5)
        
        # Adjust spawn probability based on density - increased for more traffic
        self.car_spawn_probability = 0.015 + (self.current_traffic_density * 0.05)
    
    def _update_day_night_effect(self):
        """Update day/night overlay alpha based on time."""
        hour = self.simulation_time.hour
        
        # Night time (20:00 - 06:00)
        if hour >= 20 or hour < 6:
            # Calculate darkness level
            if hour >= 20:
                darkness = min(150, (hour - 20) * 30 + 30)
            elif hour < 4:
                darkness = 150
            else:  # 4-6 AM, getting lighter
                darkness = max(0, 150 - (hour - 4) * 50)
            self.day_night_overlay_alpha = darkness
        else:
            self.day_night_overlay_alpha = 0
    
    def get_time_period_name(self):
        """Get a human-readable name for the current time period (Portuguese)."""
        hour = self.simulation_time.hour
        
        if 5 <= hour < 7:
            return "Madrugada"
        elif 7 <= hour < 9:
            return "Hora de Ponta Manhã"
        elif 9 <= hour < 12:
            return "Meio da Manhã"
        elif 12 <= hour < 14:
            return "Hora de Almoço"
        elif 14 <= hour < 17:
            return "Tarde"
        elif 17 <= hour < 19:
            return "Hora de Ponta Tarde"
        elif 19 <= hour < 21:
            return "Fim de Tarde"
        elif 21 <= hour < 24:
            return "Noite"
        else:  # 0-5
            return "Alta Noite"
    
    def increase_time_speed(self):
        """Increase simulation speed."""
        if self.time_speed_index < len(self.time_speed_options) - 1:
            self.time_speed_index += 1
            self.time_speed = self.time_speed_options[self.time_speed_index]
            print(f"[TEMPO] Velocidade: {self.time_speed}x")
    
    def decrease_time_speed(self):
        """Decrease simulation speed."""
        if self.time_speed_index > 0:
            self.time_speed_index -= 1
            self.time_speed = self.time_speed_options[self.time_speed_index]
            print(f"[TEMPO] Velocidade: {self.time_speed}x")
    
    def toggle_pause(self):
        """Toggle pause state."""
        self.is_paused = not self.is_paused
        print(f"[TEMPO] {'PAUSADO' if self.is_paused else 'RETOMADO'}")
    
    def set_time_speed(self, speed_index):
        """Set time speed to a specific index."""
        if 0 <= speed_index < len(self.time_speed_options):
            self.time_speed_index = speed_index
            self.time_speed = self.time_speed_options[self.time_speed_index]
            print(f"[TEMPO] Velocidade: {self.time_speed}x")
    
    def set_simulation_hour(self, hour):
        """Set simulation to a specific hour."""
        self.simulation_time = self.simulation_time.replace(hour=hour, minute=0, second=0)
        self._update_traffic_density()
        self._update_day_night_effect()
        print(f"[TEMPO] Definido para {hour:02d}:00")
    
    def should_spawn_car(self):
        """Determine if a new car should spawn based on traffic density."""
        if self.is_paused:
            return False
        return random.random() < self.car_spawn_probability
    
    def get_traffic_level_name(self):
        """Get traffic level as a descriptive name (Portuguese)."""
        density = self.current_traffic_density
        if density < 0.2:
            return "Muito Baixo"
        elif density < 0.4:
            return "Baixo"
        elif density < 0.6:
            return "Moderado"
        elif density < 0.8:
            return "Alto"
        else:
            return "Muito Alto"

    def handle_keyboard_events(self, event):
        """Handle keyboard events for disruption triggers and time controls."""
        if event.type == pygame.KEYDOWN:
            # F1 - Toggle help overlay
            if event.key == pygame.K_F1:
                self.show_help = not self.show_help
                print(f"[AMBIENTE] Painel de ajuda {'visível' if self.show_help else 'oculto'}")
            
            # F9 - Next display/monitor
            elif event.key == pygame.K_F9:
                next_display = (self.display_index + 1) % len(self.available_displays)
                self.switch_display(next_display)
            
            # F10 - Previous display/monitor
            elif event.key == pygame.K_F10:
                prev_display = (self.display_index - 1) % len(self.available_displays)
                self.switch_display(prev_display)
            
            # F11 - Toggle fullscreen
            elif event.key == pygame.K_F11:
                self.toggle_fullscreen()
            
            # F12 - Toggle FPS display
            elif event.key == pygame.K_F12:
                self.show_fps = not self.show_fps
            
            # ============================================================
            # CONTROLOS DE TEMPO
            # ============================================================
            
            # SPACE - Pause/Resume
            elif event.key == pygame.K_SPACE:
                self.toggle_pause()
            
            # + / = - Increase speed
            elif event.key in [pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS]:
                self.increase_time_speed()
            
            # - - Decrease speed
            elif event.key in [pygame.K_MINUS, pygame.K_KP_MINUS]:
                self.decrease_time_speed()
            
            # F2 - Realtime (1x)
            elif event.key == pygame.K_F2:
                self.set_time_speed(1)  # 1x
                print("[TEMPO] Definido para TEMPO REAL (1x)")
            
            # F3 - Fast (10x)
            elif event.key == pygame.K_F3:
                self.set_time_speed(4)  # 10x
                print("[TEMPO] Definido para RÁPIDO (10x)")
            
            # F4 - Ultra fast (60x - 1 min/sec)
            elif event.key == pygame.K_F4:
                self.set_time_speed(6)  # 60x
                print("[TEMPO] Definido para ULTRA RÁPIDO (60x)")
            
            # F5-F8 - Set specific hours
            elif event.key == pygame.K_F5:
                self.set_simulation_hour(6)  # Early morning
            elif event.key == pygame.K_F6:
                self.set_simulation_hour(8)  # Morning rush
            elif event.key == pygame.K_F7:
                self.set_simulation_hour(12)  # Noon
            elif event.key == pygame.K_F8:
                self.set_simulation_hour(18)  # Evening rush
            
            # ============================================================
            # CONTROLOS DE PERTURBAÇÕES
            # ============================================================
            
            # Tab - Cycle through intersections
            elif event.key == pygame.K_TAB:
                self.selected_intersection_index = (self.selected_intersection_index + 1) % len(INTERSECTION_IDS)
                selected = INTERSECTION_IDS[self.selected_intersection_index]
                selected_pt = INTERSECTION_NAMES_PT.get(selected, selected)
                print(f"[AMBIENTE] Cruzamento selecionado: {selected_pt}")
            
            # 1 - Trigger Accident at selected intersection
            elif event.key == pygame.K_1:
                self._trigger_disruption(DisruptionType.ACCIDENT)
            
            # 2 - Trigger Construction at selected intersection
            elif event.key == pygame.K_2:
                self._trigger_disruption(DisruptionType.CONSTRUCTION)
            
            # 3 - Toggle Bad Weather (global)
            elif event.key == pygame.K_3:
                self._toggle_global_disruption(DisruptionType.BAD_WEATHER)
            
            # 4 - Trigger Road Closure at selected intersection
            elif event.key == pygame.K_4:
                self._trigger_disruption(DisruptionType.ROAD_CLOSURE)
            
            # 5 - Trigger Special Event at selected intersection
            elif event.key == pygame.K_5:
                self._trigger_disruption(DisruptionType.SPECIAL_EVENT)
            
            # 0 - Clear disruption at selected intersection
            elif event.key == pygame.K_0:
                self._clear_disruption()
            
            # C - Clear all disruptions
            elif event.key == pygame.K_c:
                self._clear_all_disruptions()
            
            # R - Trigger random disruption at random intersection
            elif event.key == pygame.K_r:
                self._trigger_random_disruption()

    def _trigger_disruption(self, disruption_type):
        """Trigger a disruption at the selected intersection."""
        intersection_id = INTERSECTION_IDS[self.selected_intersection_index]
        intersection_pt = INTERSECTION_NAMES_PT.get(intersection_id, intersection_id)
        disruption_pt = DISRUPTION_LABELS_PT.get(disruption_type, disruption_type)
        
        # If same disruption already active, remove it
        if self.active_disruptions.get(intersection_id) == disruption_type:
            self._clear_disruption()
            return
        
        self.active_disruptions[intersection_id] = disruption_type
        self.disruption_start_times[intersection_id] = datetime.now()
        
        # Activate crash visual for accident
        if disruption_type == DisruptionType.ACCIDENT:
            self.activate_map_crash(intersection_id)
        
        # Update speed modifier based on disruptions
        self._update_speed_modifier()
        
        # Record disruption to metrics
        self.metrics_manager.record_disruption(
            sim_time=self.simulation_time,
            disruption_type=disruption_type,
            intersection_id=intersection_id,
            is_global=False,
            duration_seconds=0,  # Will be calculated when cleared
            speed_modifier=self.speed_modifier
        )
        
        print(f"[PERTURBAÇÃO] {disruption_pt.upper()} ativado em {intersection_pt}")

    def _toggle_global_disruption(self, disruption_type):
        """Toggle a global disruption (affects entire map)."""
        disruption_pt = DISRUPTION_LABELS_PT.get(disruption_type, disruption_type)
        
        if self.global_disruption == disruption_type:
            self.global_disruption = DisruptionType.NONE
            print(f"[PERTURBAÇÃO] {disruption_pt.upper()} desativado (global)")
        else:
            self.global_disruption = disruption_type
            print(f"[PERTURBAÇÃO] {disruption_pt.upper()} ativado (global)")
            
            # Record global disruption to metrics
            self.metrics_manager.record_disruption(
                sim_time=self.simulation_time,
                disruption_type=disruption_type,
                intersection_id="global",
                is_global=True,
                duration_seconds=0,
                speed_modifier=self.speed_modifier
            )
        
        self._update_speed_modifier()

    def _clear_disruption(self):
        """Clear disruption at selected intersection."""
        intersection_id = INTERSECTION_IDS[self.selected_intersection_index]
        intersection_pt = INTERSECTION_NAMES_PT.get(intersection_id, intersection_id)
        
        if intersection_id in self.active_disruptions:
            disruption_type = self.active_disruptions[intersection_id]
            del self.active_disruptions[intersection_id]
            
            if intersection_id in self.disruption_start_times:
                del self.disruption_start_times[intersection_id]
            
            # Deactivate crash visual if it was an accident
            if disruption_type == DisruptionType.ACCIDENT:
                self.deactivate_map_crash()
            
            print(f"[PERTURBAÇÃO] Limpo em {intersection_pt}")
        
        self._update_speed_modifier()

    def _clear_all_disruptions(self):
        """Clear all active disruptions."""
        self.active_disruptions.clear()
        self.disruption_start_times.clear()
        self.global_disruption = DisruptionType.NONE
        self.deactivate_map_crash()
        self._update_speed_modifier()
        print("[PERTURBAÇÃO] Todas as perturbações foram limpas")

    def _trigger_random_disruption(self):
        """Trigger a random disruption at a random intersection."""
        intersection_id = random.choice(INTERSECTION_IDS)
        disruption_type = random.choice([
            DisruptionType.ACCIDENT,
            DisruptionType.CONSTRUCTION,
            DisruptionType.ROAD_CLOSURE,
            DisruptionType.SPECIAL_EVENT
        ])
        
        self.selected_intersection_index = INTERSECTION_IDS.index(intersection_id)
        self._trigger_disruption(disruption_type)

    def _update_speed_modifier(self):
        """Update speed modifier based on active disruptions."""
        # Start with normal speed
        modifier = 1.0
        
        # Global disruptions affect speed
        if self.global_disruption == DisruptionType.BAD_WEATHER:
            modifier *= 0.6  # 40% speed reduction in bad weather
        
        # Count local disruptions
        disruption_count = len(self.active_disruptions)
        if disruption_count > 0:
            # Each local disruption reduces speed slightly
            modifier *= max(0.5, 1.0 - (disruption_count * 0.1))
        
        self.speed_modifier = modifier

    def get_disruption_at_intersection(self, intersection_id):
        """Get the disruption type at a specific intersection."""
        return self.active_disruptions.get(intersection_id, DisruptionType.NONE)

    def is_intersection_blocked(self, intersection_id):
        """Check if an intersection is blocked (road closure or accident)."""
        disruption = self.get_disruption_at_intersection(intersection_id)
        return disruption in [DisruptionType.ROAD_CLOSURE, DisruptionType.ACCIDENT]

    def draw_help_overlay(self):
        """Draw the help overlay showing keyboard shortcuts (Portuguese)."""
        # Semi-transparent background
        overlay = pygame.Surface((500, 620))
        overlay.fill((20, 20, 40))
        overlay.set_alpha(230)
        
        # Position in center of game surface
        x = (self.BASE_WIDTH - 500) // 2
        y = (self.BASE_HEIGHT - 620) // 2
        self.game_surface.blit(overlay, (x, y))
        
        # Draw border
        pygame.draw.rect(self.game_surface, (100, 100, 200), (x, y, 500, 620), 3)
        
        # Title
        title = self.font_large.render("CONTROLOS", True, (255, 255, 255))
        self.game_surface.blit(title, (x + 195, y + 15))
        
        # Help text (Portuguese)
        help_lines = [
            ("CONTROLOS DE TEMPO:", ""),
            ("ESPAÇO", "Pausar / Retomar"),
            ("+/-", "Acelerar / Abrandar"),
            ("F2", "Tempo real (1x)"),
            ("F3", "Rápido (10x)"),
            ("F4", "Ultra rápido (60x)"),
            ("F5", "Definir 06:00 (madrugada)"),
            ("F6", "Definir 08:00 (hora ponta)"),
            ("F7", "Definir 12:00 (meio-dia)"),
            ("F8", "Definir 18:00 (hora ponta)"),
            ("", ""),
            ("PERTURBAÇÕES:", ""),
            ("TAB", "Selecionar cruzamento"),
            ("1", "Acidente"),
            ("2", "Obras"),
            ("3", "Mau Tempo (global)"),
            ("4", "Estrada Cortada"),
            ("5", "Evento Especial"),
            ("0", "Limpar (selecionado)"),
            ("C", "Limpar TUDO"),
            ("R", "Perturbação aleatória"),
            ("", ""),
            ("VISUALIZAÇÃO:", ""),
            ("F9/F10", "Mudar de monitor"),
            ("F11", "Alternar ecrã inteiro"),
            ("F12", "Mostrar/ocultar FPS"),
            ("F1", "Mostrar/ocultar esta ajuda"),
            ("ESC", "Sair da simulação"),
        ]
        
        y_offset = 50
        for key, description in help_lines:
            if key in ["CONTROLOS DE TEMPO:", "PERTURBAÇÕES:", "VISUALIZAÇÃO:"]:
                text = self.font_medium.render(key, True, (255, 200, 100))
                self.game_surface.blit(text, (x + 20, y + y_offset))
            elif key:
                # Key
                key_text = self.font_medium.render(f"[{key}]", True, (150, 255, 150))
                self.game_surface.blit(key_text, (x + 20, y + y_offset))
                # Description
                desc_text = self.font_small.render(description, True, (200, 200, 200))
                self.game_surface.blit(desc_text, (x + 140, y + y_offset + 2))
            y_offset += 20
        
        # Current status
        selected = INTERSECTION_IDS[self.selected_intersection_index]
        selected_pt = INTERSECTION_NAMES_PT.get(selected, selected)
        selection_text = self.font_medium.render(f"Selecionado: {selected_pt}", True, (100, 255, 100))
        self.game_surface.blit(selection_text, (x + 20, y + 585))

    def draw_time_display(self):
        """Draw the simulation time and controls at the top right."""
        # Background panel
        pygame.draw.rect(self.game_surface, (20, 20, 40), (990, 5, 285, 85), border_radius=8)
        pygame.draw.rect(self.game_surface, (60, 60, 100), (990, 5, 285, 85), 2, border_radius=8)
        
        # Time display
        time_str = self.simulation_time.strftime("%H:%M:%S")
        time_text = self.font_time.render(time_str, True, (255, 255, 255))
        self.game_surface.blit(time_text, (1000, 10))
        
        # Date display
        date_str = self.simulation_time.strftime("%d/%m/%Y")
        date_text = self.font_small.render(date_str, True, (180, 180, 180))
        self.game_surface.blit(date_text, (1140, 20))
        
        # Speed indicator (Portuguese)
        if self.is_paused:
            speed_str = "PAUSADO"
            speed_color = (255, 100, 100)
        elif self.time_speed == 1:
            speed_str = "TEMPO REAL"
            speed_color = (100, 255, 100)
        else:
            speed_str = f"VELOCIDADE {self.time_speed}x"
            speed_color = (255, 255, 100)
        
        speed_text = self.font_medium.render(speed_str, True, speed_color)
        self.game_surface.blit(speed_text, (1000, 50))
        
        # Time period and traffic level (Portuguese)
        period = self.get_time_period_name()
        traffic = self.get_traffic_level_name()
        info_str = f"{period} | Tráfego: {traffic}"
        info_text = self.font_small.render(info_str, True, (150, 150, 200))
        self.game_surface.blit(info_text, (1000, 72))

    def draw_fps_display(self):
        """Draw FPS counter."""
        if self.show_fps:
            fps = self.clock.get_fps()
            fps_text = self.font_small.render(f"FPS: {fps:.0f}", True, (255, 255, 255))
            pygame.draw.rect(self.game_surface, (20, 20, 40), (5, 5, 70, 22), border_radius=4)
            self.game_surface.blit(fps_text, (10, 8))

    def draw_disruption_indicators(self):
        """Draw visual indicators for active disruptions."""
        # Draw selected intersection highlight
        selected_id = INTERSECTION_IDS[self.selected_intersection_index]
        center = self.intersection_centers[selected_id]
        pygame.draw.circle(self.game_surface, (255, 255, 0), center, 85, 3)  # Yellow selection ring
        
        # Draw disruption indicators at each intersection
        for intersection_id, disruption_type in self.active_disruptions.items():
            center = self.intersection_centers[intersection_id]
            color = self.disruption_colors[disruption_type]
            
            # Draw filled indicator circle
            pygame.draw.circle(self.game_surface, color, center, 20)
            pygame.draw.circle(self.game_surface, (255, 255, 255), center, 20, 2)
            
            # Draw disruption type label (Portuguese abbreviation)
            label_map = {
                DisruptionType.ACCIDENT: "ACI",
                DisruptionType.CONSTRUCTION: "OBR",
                DisruptionType.BAD_WEATHER: "TMP",
                DisruptionType.ROAD_CLOSURE: "CRT",
                DisruptionType.SPECIAL_EVENT: "EVT",
            }
            label = label_map.get(disruption_type, "???")
            text = self.font_small.render(label, True, (255, 255, 255))
            text_rect = text.get_rect(center=(center[0], center[1] - 35))
            self.game_surface.blit(text, text_rect)
        
        # Draw global disruption indicator
        if self.global_disruption != DisruptionType.NONE:
            # Draw weather overlay effect
            if self.global_disruption == DisruptionType.BAD_WEATHER:
                weather_overlay = pygame.Surface((self.BASE_WIDTH, self.BASE_HEIGHT))
                weather_overlay.fill((100, 100, 150))
                weather_overlay.set_alpha(50)
                self.game_surface.blit(weather_overlay, (0, 0))
            
            # Draw global status bar (Portuguese)
            disruption_pt = DISRUPTION_LABELS_PT.get(self.global_disruption, self.global_disruption)
            status_text = f"GLOBAL: {disruption_pt.upper()}"
            text = self.font_medium.render(status_text, True, self.disruption_colors[self.global_disruption])
            pygame.draw.rect(self.game_surface, (30, 30, 50), (10, 30, 280, 30))
            self.game_surface.blit(text, (20, 35))
        
        # Draw status bar with current info
        self._draw_status_bar()

    def _draw_status_bar(self):
        """Draw status bar at bottom of screen (Portuguese)."""
        # Background
        pygame.draw.rect(self.game_surface, (30, 30, 50), (0, 690, self.BASE_WIDTH, 30))
        
        # Info text
        selected = INTERSECTION_IDS[self.selected_intersection_index]
        selected_pt = INTERSECTION_NAMES_PT.get(selected, selected)
        active_count = len(self.active_disruptions)
        density_percent = int(self.current_traffic_density * 100)
        
        status = f"Selecionado: {selected_pt} | Perturbações: {active_count} | Densidade: {density_percent}% | Prima F1 para Ajuda"
        text = self.font_small.render(status, True, (200, 200, 200))
        self.game_surface.blit(text, (10, 695))
        
        # Disruption legend (compact)
        legend_x = 950
        for dtype, color in self.disruption_colors.items():
            if dtype != DisruptionType.NONE:
                pygame.draw.circle(self.game_surface, color, (legend_x, 705), 6)
                legend_x += 15

    def draw_day_night_overlay(self):
        """Draw day/night lighting effect."""
        if self.day_night_overlay_alpha > 0:
            night_overlay = pygame.Surface((self.BASE_WIDTH, self.BASE_HEIGHT))
            night_overlay.fill((0, 0, 30))
            night_overlay.set_alpha(self.day_night_overlay_alpha)
            self.game_surface.blit(night_overlay, (0, 0))

    def collision_sprite(self, sprite):
        if pygame.sprite.spritecollide(sprite, self.intersections, False):
            return True
        else:
            return False

    # persiste dados de espera em ficheiro CSV para análise posterior
    def write_on_csv(self, data):
        file_name = "espera_carros_lista.csv"

        with open(file_name, 'a', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerows(data)

        print('Registos guardados no ficheiro: ' + file_name)

    # deteta colisão entre veículo e zona de semáforo
    def collision_traffic_light(self, sprite):
        coll = pygame.sprite.spritecollide(sprite, self.traffic_lights, False)
        if coll:
            return (True, coll[0].id)
        else:
            return (False, 0)

    # processa ciclo de renderização da simulação
    def update_map(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.write_on_csv(self.cars_stopped_times)
                self.save_all_metrics()
                pygame.quit()
                exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.write_on_csv(self.cars_stopped_times)
                    self.save_all_metrics()
                    pygame.quit()
                    exit()
                else:
                    self.handle_keyboard_events(event)
            elif event.type == pygame.VIDEORESIZE:
                # Handle window resize (only in windowed mode)
                if not self.fullscreen:
                    self.screen_width = event.w
                    self.screen_height = event.h
                    self.screen = pygame.display.set_mode(
                        (self.screen_width, self.screen_height),
                        pygame.DOUBLEBUF | pygame.RESIZABLE,
                        vsync=1
                    )
                    self._calculate_scaling()
        
        # Update simulation time
        self.update_simulation_time()
        
        # Record metrics periodically
        self._record_metrics_periodically()

        # ============================================================
        # RENDER TO GAME SURFACE (at base resolution)
        # ============================================================
        
        # Draw background
        self.game_surface.blit(self.bg_surf, (0, 0))
        
        # Draw intersections (for collision detection, usually invisible)
        # self.intersections.draw(self.game_surface)

        if self.map_crash:
            self.collisions.draw(self.game_surface)

        # renderiza todos os semáforos ativos
        for tl in self.traffic_lights:
            tl.screen = self.game_surface  # Ensure traffic lights draw to game surface
            tl.draw()

        # renderiza veículos comuns
        for car in self.cars:
            car.sprites()[0].screen = self.game_surface  # Ensure cars draw to game surface
            car.sprites()[0].draw()

        # renderiza veículos de emergência
        for emergency_car in self.emergency_cars:
            emergency_car.sprites()[0].screen = self.game_surface
            emergency_car.sprites()[0].draw()

        # Draw day/night effect
        self.draw_day_night_overlay()

        # Draw disruption indicators
        self.draw_disruption_indicators()
        
        # Draw time display
        self.draw_time_display()
        
        # Draw FPS
        self.draw_fps_display()
        
        # Draw help overlay if active
        if self.show_help:
            self.draw_help_overlay()

        # ============================================================
        # SCALE AND DISPLAY
        # ============================================================
        
        # Clear the actual screen (for letterboxing)
        self.screen.fill((0, 0, 0))
        
        # Scale the game surface to fit the screen
        if self.scale != 1.0:
            scaled_surface = pygame.transform.smoothscale(
                self.game_surface, 
                (self.scaled_width, self.scaled_height)
            )
        else:
            scaled_surface = self.game_surface
        
        # Blit centered on screen
        self.screen.blit(scaled_surface, (self.offset_x, self.offset_y))

        pygame.display.flip()
        
        # Use vsync (clock.tick with 0 lets vsync control the framerate)
        if self.target_fps > 0:
            self.clock.tick(self.target_fps)
        else:
            self.clock.tick()  # Let vsync handle it

    def add_car(self, car_id):
        car = pygame.sprite.GroupSingle()
        new_car = Car(self.game_surface, str(car_id).replace("carro_", "").replace("@localhost", ""))
        car.add(new_car)
        self.cars.append(car)

        self.car_positions[str(car_id)] = car.sprites()[0].get_car_position()

        return car

    def get_car_by_id(self, car_id):
        for car_group in self.cars:
            if car_group.sprites() and car_group.sprites()[0].id:
                car_full_id = 'car_' + car_group.sprites()[0].id + "@localhost"
                if car_full_id == car_id:
                    return car_group
        return None

    # atualiza coordenadas e orientação de veículo específico
    def update_car_position(self, car_id, car_pos):
        old_pos = self.car_positions.get(car_id)
        self.car_positions[car_id] = (car_pos[0], car_pos[1], car_pos[2])
        
        # Track position for speed calculation
        current_time = datetime.now()
        self.car_position_history[car_id].append((car_pos[0], car_pos[1], current_time))
        
        # Keep only last 10 positions for speed calculation
        if len(self.car_position_history[car_id]) > 10:
            self.car_position_history[car_id].pop(0)
        
        # Calculate speed
        self._update_car_speed(car_id)
        
        # Check if car passed through an intersection
        self._check_intersection_passage(car_id, car_pos)

    def _update_car_speed(self, car_id):
        """Calculate car speed based on position history."""
        history = self.car_position_history[car_id]
        if len(history) >= 2:
            # Calculate speed from last two positions
            pos1 = history[-2]
            pos2 = history[-1]
            
            distance = ((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2)**0.5
            time_diff = (pos2[2] - pos1[2]).total_seconds()
            
            if time_diff > 0:
                self.car_speeds[car_id] = distance / time_diff

    def _check_intersection_passage(self, car_id, car_pos):
        """Check if a car has passed through an intersection."""
        x, y = car_pos[0], car_pos[1]
        
        for intersection_id, bounds in self.intersection_bounds.items():
            ix, iy, iw, ih = bounds
            
            # Check if car is inside intersection bounds
            if ix <= x <= ix + iw and iy <= y <= iy + ih:
                # Car is in intersection
                if car_id not in self.cars_passed_intersections[intersection_id]:
                    self.record_vehicle_passed(intersection_id, car_id)

    def record_vehicle_passed(self, intersection_id, car_id=None):
        """Record that a vehicle has passed through an intersection."""
        self.vehicles_passed_per_intersection[intersection_id] += 1
        if car_id:
            self.cars_passed_intersections[intersection_id].add(car_id)
        
        # Also record to metrics manager
        self.metrics_manager.record_traffic_flow(
            sim_time=self.simulation_time,
            intersection_id=intersection_id,
            vehicles_passed=1,
            direction="through",
            vehicle_type="car" if car_id and "carro" in str(car_id) else "emergency"
        )

    def _record_metrics_periodically(self):
        """Record system metrics periodically for analysis and ML training."""
        now = datetime.now()
        
        # Only record every few seconds of real time
        if (now - self.last_metrics_save).total_seconds() < self.metrics_save_interval:
            return
        
        self.last_metrics_save = now
        
        # Calculate total stopped vehicles
        total_stopped = sum(len(cars) for cars in self.cars_stopped_at_tl.values())
        
        # Calculate average waiting time for current session
        total_wait = 0
        for stop in self.cars_stopped_times[-100:]:  # Last 100 stops
            try:
                time_parts = stop[2].split(":")
                total_wait += int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
            except:
                pass
        avg_wait = total_wait / max(1, len(self.cars_stopped_times[-100:]))
        
        # Record system snapshot
        self.metrics_manager.record_system_snapshot(
            sim_time=self.simulation_time,
            total_cars=len(self.cars),
            total_emergency_cars=len(self.emergency_cars),
            total_stopped=total_stopped,
            avg_speed=self.get_average_speed(),
            avg_waiting_time=avg_wait,
            traffic_density=self.current_traffic_density,
            active_disruptions=len(self.active_disruptions),
            global_disruption=self.global_disruption,
            speed_modifier=self.speed_modifier,
            time_speed_multiplier=self.time_speed,
            is_paused=self.is_paused
        )
        
        # Record congestion and intersection metrics for each intersection
        for intersection_id in INTERSECTION_IDS:
            congestion = self.calculate_congestion_level(intersection_id)
            
            # Count stopped at this intersection
            stopped_at_intersection = 0
            for tl_id, cars in self.cars_stopped_at_tl.items():
                if intersection_id in tl_id:
                    stopped_at_intersection += len(cars)
            
            # Record congestion
            self.metrics_manager.record_congestion(
                sim_time=self.simulation_time,
                intersection_id=intersection_id,
                congestion_level=congestion,
                stopped_vehicles=stopped_at_intersection,
                traffic_density=self.current_traffic_density
            )
            
            # Record intersection metrics
            has_disruption = intersection_id in self.active_disruptions
            disruption_type = self.active_disruptions.get(intersection_id, "none")
            
            self.metrics_manager.record_intersection_metrics(
                sim_time=self.simulation_time,
                intersection_id=intersection_id,
                vehicles_passed_total=self.vehicles_passed_per_intersection.get(intersection_id, 0),
                congestion_level=congestion,
                has_disruption=has_disruption,
                disruption_type=disruption_type,
                vertical_light_state="unknown",  # Would need traffic light agent info
                horizontal_light_state="unknown"
            )

    def save_all_metrics(self):
        """Save all metrics to disk and create session summary."""
        # Flush all buffers
        self.metrics_manager.flush_all()
        
        # Save session summary
        self.metrics_manager.save_session_summary(self.get_metrics_summary())
        
        # Print file locations
        print("\n[METRICS] Ficheiros de dados guardados:")
        for name, path in self.metrics_manager.get_session_files().items():
            print(f"   {name}: {path}")

    def calculate_congestion_level(self, intersection_id):
        """
        Calculate congestion level for an intersection.
        Returns a value between 0 (no congestion) and 1 (high congestion).
        """
        # Count cars stopped at this intersection's traffic lights
        stopped_count = 0
        for tl_id, cars in self.cars_stopped_at_tl.items():
            if intersection_id in tl_id:
                stopped_count += len(cars)
        
        # Add penalty for active disruptions
        if intersection_id in self.active_disruptions:
            stopped_count += 3  # Disruption adds to perceived congestion
        
        # Normalize: assume max 10 cars per intersection for full congestion
        congestion = min(1.0, stopped_count / 10.0)
        self.congestion_levels[intersection_id] = congestion
        
        return congestion

    def get_average_speed(self):
        """Get the average speed of all cars currently in the simulation."""
        if not self.car_speeds:
            return 0.0
        
        speeds = [s for s in self.car_speeds.values() if s > 0]
        if not speeds:
            return 0.0
        
        return sum(speeds) / len(speeds) * self.speed_modifier

    def get_metrics_summary(self):
        """
        Get a summary of all performance metrics.
        Returns a dictionary with key metrics.
        """
        # Calculate simulation duration
        duration = (datetime.now() - self.simulation_start_time).total_seconds()
        
        # Calculate average waiting time
        total_wait_seconds = 0
        for stop in self.cars_stopped_times:
            time_str = stop[2]  # Format: "0:00:05"
            time_parts = time_str.split(":")
            hours = int(time_parts[0])
            minutes = int(time_parts[1])
            seconds = int(time_parts[2])
            total_wait_seconds += hours * 3600 + minutes * 60 + seconds
        
        avg_wait = total_wait_seconds / len(self.cars_stopped_times) if self.cars_stopped_times else 0
        
        # Update congestion levels
        for intersection_id in INTERSECTION_IDS:
            self.calculate_congestion_level(intersection_id)
        
        return {
            "simulation_duration_seconds": duration,
            "simulation_time": self.simulation_time.strftime("%Y-%m-%d %H:%M:%S"),
            "time_speed": self.time_speed,
            "total_stops": len(self.cars_stopped_times),
            "average_waiting_time_seconds": avg_wait,
            "total_waiting_time_seconds": total_wait_seconds,
            "vehicles_passed_per_intersection": dict(self.vehicles_passed_per_intersection),
            "congestion_levels": dict(self.congestion_levels),
            "average_speed": self.get_average_speed(),
            "total_cars_active": len(self.cars),
            "total_emergency_cars_active": len(self.emergency_cars),
            "active_disruptions": dict(self.active_disruptions),
            "global_disruption": self.global_disruption,
            "traffic_density": self.current_traffic_density,
        }

    def print_metrics_summary(self):
        """Print a formatted summary of performance metrics (Portuguese)."""
        metrics = self.get_metrics_summary()
        
        print("\n" + "=" * 80)
        print("RESUMO DE MÉTRICAS DE DESEMPENHO")
        print("=" * 80)
        
        print(f"\n📊 VISÃO GERAL DA SIMULAÇÃO")
        print(f"   Duração Real: {metrics['simulation_duration_seconds']:.1f} segundos")
        print(f"   Tempo Simulado: {metrics['simulation_time']}")
        print(f"   Velocidade Tempo: {metrics['time_speed']}x")
        print(f"   Carros Ativos: {metrics['total_cars_active']}")
        print(f"   Veículos Emergência Ativos: {metrics['total_emergency_cars_active']}")
        print(f"   Densidade Tráfego: {metrics['traffic_density']:.0%}")
        
        print(f"\n⏱️ TEMPOS DE ESPERA")
        print(f"   Total de Paragens: {metrics['total_stops']}")
        print(f"   Espera Média: {metrics['average_waiting_time_seconds']:.2f} segundos")
        print(f"   Tempo Total Espera: {metrics['total_waiting_time_seconds']} segundos")
        
        print(f"\n🚗 VEÍCULOS POR CRUZAMENTO")
        for intersection_id in INTERSECTION_IDS:
            count = metrics['vehicles_passed_per_intersection'].get(intersection_id, 0)
            intersection_pt = INTERSECTION_NAMES_PT.get(intersection_id, intersection_id)
            print(f"   {intersection_pt}: {count} veículos")
        
        print(f"\n🚦 NÍVEIS DE CONGESTIONAMENTO (0=baixo, 1=alto)")
        for intersection_id in INTERSECTION_IDS:
            level = metrics['congestion_levels'].get(intersection_id, 0)
            bar = "█" * int(level * 10) + "░" * (10 - int(level * 10))
            intersection_pt = INTERSECTION_NAMES_PT.get(intersection_id, intersection_id)
            print(f"   {intersection_pt}: [{bar}] {level:.2f}")
        
        print(f"\n🏎️ VELOCIDADE MÉDIA: {metrics['average_speed']:.2f} pixels/segundo")
        
        print(f"\n⚠️ PERTURBAÇÕES")
        if metrics['active_disruptions']:
            for intersection_id, dtype in metrics['active_disruptions'].items():
                intersection_pt = INTERSECTION_NAMES_PT.get(intersection_id, intersection_id)
                disruption_pt = DISRUPTION_LABELS_PT.get(dtype, dtype)
                print(f"   {intersection_pt}: {disruption_pt}")
        else:
            print("   Sem perturbações locais ativas")
        
        global_pt = DISRUPTION_LABELS_PT.get(metrics['global_disruption'], metrics['global_disruption'])
        print(f"   Global: {global_pt}")
        
        print("=" * 80)

    # retorna dicionário com localização de todos os veículos
    def get_car_positions(self):
        return self.car_positions

    def add_traffic_light(self, tl_jid, tl_id, tl_pos, angle):
        tl = TrafficLight(self.game_surface, tl_id, tl_pos, angle)
        self.traffic_lights.add(tl)

        self.traffic_lights_objects[str(tl_id)] = tl
        self.traffic_lights_agents_tl[str(tl_id)] = tl_jid
        self.traffic_lights_status[str(tl_id)] = tl.get_status()

        return tl

    # modifica fase luminosa de semáforo específico
    def update_traffic_light_status(self, tl_id, status):
        self.traffic_lights_status[tl_id] = status

    # consulta estado atual de semáforo por identificador
    def get_traffic_light_status(self, tl_id):
        return self.traffic_lights_status[str(tl_id)]

    # obtém identificador do agente responsável por semáforo
    def get_traffic_light_jid_by_id(self, tl_id):
        return self.traffic_lights_agents_tl[str(tl_id)]

    # instancia novo veículo de emergência no ambiente
    # devolve referência para controlo pelo agente correspondente
    def add_emergency_car(self, car_id):
        car = pygame.sprite.GroupSingle()
        car.add(EmergencyCar(self.game_surface, str(car_id).replace("emergencia_carro_", "").replace("@localhost", "")))
        self.emergency_cars.append(car)
        
        # Track position like regular cars
        self.car_positions[str(car_id)] = car.sprites()[0].get_car_position()

        return car

    # ativa condição de bloqueio por acidente em cruzamento
    def activate_map_crash(self, crossing):
        self.map_crash = True
        self.crash_position = random.choice(CRASH_POSITIONS[crossing])

        self.crash_location = crossing + "_" + self.crash_position[0]

        self.collisions = pygame.sprite.Group()
        self.collisions.add(Crash(self.crash_position[1]))

    # remove condição de bloqueio por acidente
    def deactivate_map_crash(self):
        self.map_crash = False

    # calcula faixa bloqueada baseada em posição relativa do acidente
    def determine_restricted_turn(self, crash_position, car_position):
        restrictions = {
            ('r', 't'): "l",
            ('r', 'b'): "r",
            ('r', 'l'): "c",
            ('l', 't'): "r",
            ('l', 'b'): "l",
            ('l', 'r'): "c",
            ('t', 'l'): "l",
            ('t', 'r'): "r",
            ('t', 'b'): "c",
            ('b', 'l'): "r",
            ('b', 'r'): "l",
            ('b', 't'): "c",
        }

        return restrictions.get((crash_position, car_position), "")

    # verifica se veículo enfrenta restrição de trajetória devido a acidente
    def get_blocked_turn(self, tl, crash):
        tl_to_open_txt_arr = str(tl).split("_")
        crash_location_txt_arr = str(crash).split("_")

        blocked_turn = ""
        if self.map_crash and (tl_to_open_txt_arr[0] + tl_to_open_txt_arr[1]) == (crash_location_txt_arr[0] + crash_location_txt_arr[1]):
            blocked_turn = self.determine_restricted_turn(crash_location_txt_arr[2], tl_to_open_txt_arr[2])

        return blocked_turn
