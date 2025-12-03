import csv
import random
import pygame
from datetime import datetime, timedelta
from collections import defaultdict

from Map.Car import Car
from Map.Crash import Crash
from Map.EmergencyCar import EmergencyCar

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

# Disruption types
class DisruptionType:
    NONE = "none"
    ACCIDENT = "accident"
    CONSTRUCTION = "construction"
    BAD_WEATHER = "bad_weather"
    ROAD_CLOSURE = "road_closure"
    SPECIAL_EVENT = "special_event"


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
    def __init__(self):
        # estabelece janela de visualização e recursos gráficos base
        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((1280, 720))
        pygame.display.set_caption("Traffic Management System - Press F1 for Help")
        self.bg_surf = pygame.image.load('Map/Resources/fundo.png').convert()
        self.clock = pygame.time.Clock()
        
        # Fonts for UI
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
        # 24-HOUR TIME SIMULATION
        # ============================================================
        self.simulation_time = datetime(2024, 1, 1, 7, 0, 0)  # Start at 7:00 AM
        self.time_speed_options = [0, 1, 2, 5, 10, 30, 60, 120, 300, 600]  # Speed multipliers
        self.time_speed_index = 3  # Default: 5x speed (1 real second = 5 sim seconds)
        self.time_speed = self.time_speed_options[self.time_speed_index]
        self.last_time_update = datetime.now()
        self.is_paused = False
        
        # Traffic density based on time
        self.current_traffic_density = 0.5
        self.car_spawn_probability = 0.02  # Base probability per frame
        
        # Day/night visual effects
        self.day_night_overlay_alpha = 0
        
        # ============================================================
        # DISRUPTION MANAGEMENT
        # ============================================================
        self.show_help = False  # F1 toggles help overlay
        self.active_disruptions = {}  # {intersection_id: DisruptionType}
        self.disruption_start_times = {}  # {intersection_id: datetime}
        self.global_disruption = DisruptionType.NONE  # Global disruption (e.g., weather)
        self.speed_modifier = 1.0  # Speed reduction due to disruptions (1.0 = normal)
        
        # Disruption visual indicators
        self.disruption_colors = {
            DisruptionType.NONE: (0, 255, 0),        # Green
            DisruptionType.ACCIDENT: (255, 0, 0),    # Red
            DisruptionType.CONSTRUCTION: (255, 165, 0),  # Orange
            DisruptionType.BAD_WEATHER: (100, 100, 255),  # Light Blue
            DisruptionType.ROAD_CLOSURE: (128, 0, 128),   # Purple
            DisruptionType.SPECIAL_EVENT: (255, 255, 0),  # Yellow
        }
        
        # Selected intersection for disruption placement
        self.selected_intersection_index = 0
        
        # ============================================================
        # ENHANCED PERFORMANCE METRICS
        # ============================================================
        
        # Vehicles passed per intersection
        self.vehicles_passed_per_intersection = defaultdict(int)
        
        # Congestion levels per intersection (updated periodically)
        self.congestion_levels = defaultdict(float)
        
        # Position tracking for speed calculation
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

    # ============================================================
    # TIME SIMULATION METHODS
    # ============================================================
    
    def update_simulation_time(self):
        """Update the simulation clock based on time speed."""
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
        
        # Adjust spawn probability based on density
        self.car_spawn_probability = 0.005 + (self.current_traffic_density * 0.03)
    
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
        """Get a human-readable name for the current time period."""
        hour = self.simulation_time.hour
        
        if 5 <= hour < 7:
            return "Early Morning"
        elif 7 <= hour < 9:
            return "Morning Rush"
        elif 9 <= hour < 12:
            return "Mid-Morning"
        elif 12 <= hour < 14:
            return "Lunch Time"
        elif 14 <= hour < 17:
            return "Afternoon"
        elif 17 <= hour < 19:
            return "Evening Rush"
        elif 19 <= hour < 21:
            return "Evening"
        elif 21 <= hour < 24:
            return "Night"
        else:  # 0-5
            return "Late Night"
    
    def increase_time_speed(self):
        """Increase simulation speed."""
        if self.time_speed_index < len(self.time_speed_options) - 1:
            self.time_speed_index += 1
            self.time_speed = self.time_speed_options[self.time_speed_index]
            print(f"[TIME] Speed: {self.time_speed}x")
    
    def decrease_time_speed(self):
        """Decrease simulation speed."""
        if self.time_speed_index > 0:
            self.time_speed_index -= 1
            self.time_speed = self.time_speed_options[self.time_speed_index]
            print(f"[TIME] Speed: {self.time_speed}x")
    
    def toggle_pause(self):
        """Toggle pause state."""
        self.is_paused = not self.is_paused
        print(f"[TIME] {'PAUSED' if self.is_paused else 'RESUMED'}")
    
    def set_time_speed(self, speed_index):
        """Set time speed to a specific index."""
        if 0 <= speed_index < len(self.time_speed_options):
            self.time_speed_index = speed_index
            self.time_speed = self.time_speed_options[self.time_speed_index]
            print(f"[TIME] Speed: {self.time_speed}x")
    
    def set_simulation_hour(self, hour):
        """Set simulation to a specific hour."""
        self.simulation_time = self.simulation_time.replace(hour=hour, minute=0, second=0)
        self._update_traffic_density()
        self._update_day_night_effect()
        print(f"[TIME] Set to {hour:02d}:00")
    
    def should_spawn_car(self):
        """Determine if a new car should spawn based on traffic density."""
        if self.is_paused:
            return False
        return random.random() < self.car_spawn_probability
    
    def get_traffic_level_name(self):
        """Get traffic level as a descriptive name."""
        density = self.current_traffic_density
        if density < 0.2:
            return "Very Low"
        elif density < 0.4:
            return "Low"
        elif density < 0.6:
            return "Moderate"
        elif density < 0.8:
            return "High"
        else:
            return "Very High"

    def handle_keyboard_events(self, event):
        """Handle keyboard events for disruption triggers and time controls."""
        if event.type == pygame.KEYDOWN:
            # F1 - Toggle help overlay
            if event.key == pygame.K_F1:
                self.show_help = not self.show_help
                print(f"[ENVIRONMENT] Help overlay {'shown' if self.show_help else 'hidden'}")
            
            # ============================================================
            # TIME CONTROLS
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
                print("[TIME] Set to REALTIME (1x)")
            
            # F3 - Fast (10x)
            elif event.key == pygame.K_F3:
                self.set_time_speed(4)  # 10x
                print("[TIME] Set to FAST (10x)")
            
            # F4 - Ultra fast (60x - 1 min/sec)
            elif event.key == pygame.K_F4:
                self.set_time_speed(6)  # 60x
                print("[TIME] Set to ULTRA FAST (60x)")
            
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
            # DISRUPTION CONTROLS
            # ============================================================
            
            # Tab - Cycle through intersections
            elif event.key == pygame.K_TAB:
                self.selected_intersection_index = (self.selected_intersection_index + 1) % len(INTERSECTION_IDS)
                selected = INTERSECTION_IDS[self.selected_intersection_index]
                print(f"[ENVIRONMENT] Selected intersection: {selected}")
            
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
        
        print(f"[DISRUPTION] {disruption_type.upper()} triggered at {intersection_id}")

    def _toggle_global_disruption(self, disruption_type):
        """Toggle a global disruption (affects entire map)."""
        if self.global_disruption == disruption_type:
            self.global_disruption = DisruptionType.NONE
            print(f"[DISRUPTION] {disruption_type.upper()} cleared (global)")
        else:
            self.global_disruption = disruption_type
            print(f"[DISRUPTION] {disruption_type.upper()} activated (global)")
        
        self._update_speed_modifier()

    def _clear_disruption(self):
        """Clear disruption at selected intersection."""
        intersection_id = INTERSECTION_IDS[self.selected_intersection_index]
        
        if intersection_id in self.active_disruptions:
            disruption_type = self.active_disruptions[intersection_id]
            del self.active_disruptions[intersection_id]
            
            if intersection_id in self.disruption_start_times:
                del self.disruption_start_times[intersection_id]
            
            # Deactivate crash visual if it was an accident
            if disruption_type == DisruptionType.ACCIDENT:
                self.deactivate_map_crash()
            
            print(f"[DISRUPTION] Cleared at {intersection_id}")
        
        self._update_speed_modifier()

    def _clear_all_disruptions(self):
        """Clear all active disruptions."""
        self.active_disruptions.clear()
        self.disruption_start_times.clear()
        self.global_disruption = DisruptionType.NONE
        self.deactivate_map_crash()
        self._update_speed_modifier()
        print("[DISRUPTION] All disruptions cleared")

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
        """Draw the help overlay showing keyboard shortcuts."""
        # Semi-transparent background
        overlay = pygame.Surface((450, 550))
        overlay.fill((20, 20, 40))
        overlay.set_alpha(230)
        
        # Position in center of screen
        x = (1280 - 450) // 2
        y = (720 - 550) // 2
        self.screen.blit(overlay, (x, y))
        
        # Draw border
        pygame.draw.rect(self.screen, (100, 100, 200), (x, y, 450, 550), 3)
        
        # Title
        title = self.font_large.render("CONTROLS", True, (255, 255, 255))
        self.screen.blit(title, (x + 170, y + 15))
        
        # Help text
        help_lines = [
            ("TIME CONTROLS:", ""),
            ("SPACE", "Pause / Resume"),
            ("+/-", "Speed up / Slow down"),
            ("F2", "Realtime (1x)"),
            ("F3", "Fast (10x)"),
            ("F4", "Ultra fast (60x)"),
            ("F5", "Set to 06:00 (morning)"),
            ("F6", "Set to 08:00 (rush hour)"),
            ("F7", "Set to 12:00 (noon)"),
            ("F8", "Set to 18:00 (evening rush)"),
            ("", ""),
            ("DISRUPTIONS:", ""),
            ("TAB", "Select next intersection"),
            ("1", "Accident"),
            ("2", "Construction"),
            ("3", "Bad Weather (global)"),
            ("4", "Road Closure"),
            ("5", "Special Event"),
            ("0", "Clear (selected)"),
            ("C", "Clear ALL"),
            ("R", "Random disruption"),
            ("", ""),
            ("F1", "Toggle this help"),
            ("ESC", "Exit simulation"),
        ]
        
        y_offset = 50
        for key, description in help_lines:
            if key in ["TIME CONTROLS:", "DISRUPTIONS:"]:
                text = self.font_medium.render(key, True, (255, 200, 100))
                self.screen.blit(text, (x + 20, y + y_offset))
            elif key:
                # Key
                key_text = self.font_medium.render(f"[{key}]", True, (150, 255, 150))
                self.screen.blit(key_text, (x + 20, y + y_offset))
                # Description
                desc_text = self.font_small.render(description, True, (200, 200, 200))
                self.screen.blit(desc_text, (x + 120, y + y_offset + 2))
            y_offset += 20
        
        # Current status
        selected = INTERSECTION_IDS[self.selected_intersection_index]
        selection_text = self.font_medium.render(f"Selected: {selected}", True, (100, 255, 100))
        self.screen.blit(selection_text, (x + 20, y + 515))

    def draw_time_display(self):
        """Draw the simulation time and controls at the top right."""
        # Background panel
        pygame.draw.rect(self.screen, (20, 20, 40), (1000, 5, 275, 85), border_radius=8)
        pygame.draw.rect(self.screen, (60, 60, 100), (1000, 5, 275, 85), 2, border_radius=8)
        
        # Time display
        time_str = self.simulation_time.strftime("%H:%M:%S")
        time_text = self.font_time.render(time_str, True, (255, 255, 255))
        self.screen.blit(time_text, (1010, 10))
        
        # Date display
        date_str = self.simulation_time.strftime("%a, %b %d")
        date_text = self.font_small.render(date_str, True, (180, 180, 180))
        self.screen.blit(date_text, (1140, 20))
        
        # Speed indicator
        if self.is_paused:
            speed_str = "PAUSED"
            speed_color = (255, 100, 100)
        elif self.time_speed == 1:
            speed_str = "REALTIME"
            speed_color = (100, 255, 100)
        else:
            speed_str = f"{self.time_speed}x SPEED"
            speed_color = (255, 255, 100)
        
        speed_text = self.font_medium.render(speed_str, True, speed_color)
        self.screen.blit(speed_text, (1010, 50))
        
        # Time period and traffic level
        period = self.get_time_period_name()
        traffic = self.get_traffic_level_name()
        info_str = f"{period} | Traffic: {traffic}"
        info_text = self.font_small.render(info_str, True, (150, 150, 200))
        self.screen.blit(info_text, (1010, 72))

    def draw_disruption_indicators(self):
        """Draw visual indicators for active disruptions."""
        # Draw selected intersection highlight
        selected_id = INTERSECTION_IDS[self.selected_intersection_index]
        center = self.intersection_centers[selected_id]
        pygame.draw.circle(self.screen, (255, 255, 0), center, 85, 3)  # Yellow selection ring
        
        # Draw disruption indicators at each intersection
        for intersection_id, disruption_type in self.active_disruptions.items():
            center = self.intersection_centers[intersection_id]
            color = self.disruption_colors[disruption_type]
            
            # Draw filled indicator circle
            pygame.draw.circle(self.screen, color, center, 20)
            pygame.draw.circle(self.screen, (255, 255, 255), center, 20, 2)
            
            # Draw disruption type label
            label = disruption_type[:3].upper()
            text = self.font_small.render(label, True, (255, 255, 255))
            text_rect = text.get_rect(center=(center[0], center[1] - 35))
            self.screen.blit(text, text_rect)
        
        # Draw global disruption indicator
        if self.global_disruption != DisruptionType.NONE:
            # Draw weather overlay effect
            if self.global_disruption == DisruptionType.BAD_WEATHER:
                weather_overlay = pygame.Surface((1280, 720))
                weather_overlay.fill((100, 100, 150))
                weather_overlay.set_alpha(50)
                self.screen.blit(weather_overlay, (0, 0))
            
            # Draw global status bar
            status_text = f"GLOBAL: {self.global_disruption.upper()}"
            text = self.font_medium.render(status_text, True, self.disruption_colors[self.global_disruption])
            pygame.draw.rect(self.screen, (30, 30, 50), (10, 10, 250, 30))
            self.screen.blit(text, (20, 15))
        
        # Draw status bar with current info
        self._draw_status_bar()

    def _draw_status_bar(self):
        """Draw status bar at bottom of screen."""
        # Background
        pygame.draw.rect(self.screen, (30, 30, 50), (0, 690, 1280, 30))
        
        # Info text
        selected = INTERSECTION_IDS[self.selected_intersection_index]
        active_count = len(self.active_disruptions)
        speed_percent = int(self.speed_modifier * 100)
        density_percent = int(self.current_traffic_density * 100)
        
        status = f"Selected: {selected} | Disruptions: {active_count} | Traffic Density: {density_percent}% | Press F1 for Help"
        text = self.font_small.render(status, True, (200, 200, 200))
        self.screen.blit(text, (10, 695))
        
        # Disruption legend (compact)
        legend_x = 950
        for dtype, color in self.disruption_colors.items():
            if dtype != DisruptionType.NONE:
                pygame.draw.circle(self.screen, color, (legend_x, 705), 6)
                legend_x += 15

    def draw_day_night_overlay(self):
        """Draw day/night lighting effect."""
        if self.day_night_overlay_alpha > 0:
            night_overlay = pygame.Surface((1280, 720))
            night_overlay.fill((0, 0, 30))
            night_overlay.set_alpha(self.day_night_overlay_alpha)
            self.screen.blit(night_overlay, (0, 0))

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

        print('Records saved on file with name: ' + file_name)

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
                pygame.quit()
                exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.write_on_csv(self.cars_stopped_times)
                    pygame.quit()
                    exit()
                else:
                    self.handle_keyboard_events(event)
        
        # Update simulation time
        self.update_simulation_time()

        self.intersections.draw(self.screen)

        self.screen.blit(self.bg_surf, (0, 0))

        if self.map_crash:
            self.collisions.draw(self.screen)

        # renderiza todos os semáforos ativos
        for tl in self.traffic_lights:
            tl.draw()

        # renderiza veículos comuns
        for car in self.cars:
            car.sprites()[0].draw()

        # renderiza veículos de emergência
        for emergency_car in self.emergency_cars:
            emergency_car.sprites()[0].draw()

        # Draw day/night effect
        self.draw_day_night_overlay()

        # Draw disruption indicators
        self.draw_disruption_indicators()
        
        # Draw time display
        self.draw_time_display()
        
        # Draw help overlay if active
        if self.show_help:
            self.draw_help_overlay()

        pygame.display.update()
        self.clock.tick(60)

    def add_car(self, car_id):
        car = pygame.sprite.GroupSingle()
        car.add(Car(self.screen, str(car_id).replace("carro_", "").replace("@localhost", "")))
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
        """Print a formatted summary of performance metrics."""
        metrics = self.get_metrics_summary()
        
        print("\n" + "=" * 80)
        print("PERFORMANCE METRICS SUMMARY")
        print("=" * 80)
        
        print(f"\n📊 SIMULATION OVERVIEW")
        print(f"   Real Duration: {metrics['simulation_duration_seconds']:.1f} seconds")
        print(f"   Simulation Time: {metrics['simulation_time']}")
        print(f"   Time Speed: {metrics['time_speed']}x")
        print(f"   Active Cars: {metrics['total_cars_active']}")
        print(f"   Active Emergency Vehicles: {metrics['total_emergency_cars_active']}")
        print(f"   Traffic Density: {metrics['traffic_density']:.0%}")
        
        print(f"\n⏱️ WAITING TIMES")
        print(f"   Total Stops: {metrics['total_stops']}")
        print(f"   Average Wait: {metrics['average_waiting_time_seconds']:.2f} seconds")
        print(f"   Total Wait Time: {metrics['total_waiting_time_seconds']} seconds")
        
        print(f"\n🚗 VEHICLES PASSED PER INTERSECTION")
        for intersection_id in INTERSECTION_IDS:
            count = metrics['vehicles_passed_per_intersection'].get(intersection_id, 0)
            print(f"   {intersection_id}: {count} vehicles")
        
        print(f"\n🚦 CONGESTION LEVELS (0=low, 1=high)")
        for intersection_id in INTERSECTION_IDS:
            level = metrics['congestion_levels'].get(intersection_id, 0)
            bar = "█" * int(level * 10) + "░" * (10 - int(level * 10))
            print(f"   {intersection_id}: [{bar}] {level:.2f}")
        
        print(f"\n🏎️ AVERAGE SPEED: {metrics['average_speed']:.2f} pixels/second")
        
        print(f"\n⚠️ DISRUPTIONS")
        if metrics['active_disruptions']:
            for intersection_id, dtype in metrics['active_disruptions'].items():
                print(f"   {intersection_id}: {dtype}")
        else:
            print("   No local disruptions active")
        print(f"   Global: {metrics['global_disruption']}")
        
        print("=" * 80)

    # retorna dicionário com localização de todos os veículos
    def get_car_positions(self):
        return self.car_positions

    def add_traffic_light(self, tl_jid, tl_id, tl_pos, angle):
        tl = TrafficLight(self.screen, tl_id, tl_pos, angle)
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
        car.add(EmergencyCar(self.screen, str(car_id).replace("car_", "").replace("@localhost", "")))
        self.emergency_cars.append(car)

        #self.car_positions[str(car_id)] = car.sprites()[0].get_car_position()

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
