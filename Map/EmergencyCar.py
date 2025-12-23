# Map/EmergencyCar.py
"""
Emergency vehicle sprite that uses the same movement logic as normal cars
but doesn't stop at red lights.
"""

import math
import random
import pygame
from Models.Directions import Directions
from Map.Car import (Car, get_lane_position, _get_first_turn_for_route, 
                     _get_road_section, _get_angle_for_entry, _calculate_turn_direction)
from Map.RoadMap import get_road_map
from Models.PathFinding import get_traffic_network, get_pathfinder, get_random_destination

AMBULANCE = ['Map/Resources/Cars/ambulancia-1.png', 'Map/Resources/Cars/ambulancia-2.png']
POLICE = ['Map/Resources/Cars/policia-1.png', 'Map/Resources/Cars/policia-2.png']

# Entry points list
ENTRY_POINTS = ["south_left", "south_mid", "south_right",
                "north_left", "north_mid", "north_right",
                "west_top", "west_bottom",
                "east_top", "east_bottom"]


class EmergencyCar(pygame.sprite.Sprite):
    """Emergency vehicle that follows the same paths as regular cars but with priority.
    Emergency vehicles are 50% faster than normal cars.
    """
    # Emergency vehicles are 50% faster than normal cars
    EMERGENCY_SPEED_MULTIPLIER = 1.50
    
    def __init__(self, screen, id):
        super().__init__()

        self.animation_index = 0
        self.animation_count = 1
        self.car_type = random.choice([POLICE, AMBULANCE])

        self.id = id
        self.screen = screen
        self.base_speed = 1  # Base speed (multiplied by EMERGENCY_SPEED_MULTIPLIER for movement)
        self.car_speed = 0
        
        # A* Pathfinding
        self.network = get_traffic_network()
        self.pathfinder = get_pathfinder()
        
        # Choose entry point and calculate route first
        self.entry_point = random.choice(ENTRY_POINTS)
        self.angle = _get_angle_for_entry(self.entry_point)
        self.destination = get_random_destination(self.entry_point)
        self.route = self._calculate_route()
        self.current_route_index = 0
        self.passed_intersections = set()
        
        # Calculate first turn direction using the same logic as Car
        first_turn = _get_first_turn_for_route(self.entry_point, self.route, self.destination, self.angle, self.network)
        self.next_turn_direction = first_turn
        
        # Get appropriate lane based on first turn
        road_section = _get_road_section(self.entry_point)
        spawn_pos = get_lane_position(self.entry_point, first_turn, road_section)
        
        # Debug info
        car_type_name = "AMBULÂNCIA" if self.car_type == AMBULANCE else "POLÍCIA"
        lane_name = {Directions.LEFT: "ESQUERDA", Directions.RIGHT: "DIREITA", Directions.FORWARD: "FRENTE"}
        turn_name = lane_name.get(first_turn, "FRENTE")
        if self.route:
            print(f"[{car_type_name} {self.id}] Faixa: {turn_name} | Rota: {self.entry_point} -> {' -> '.join(self.route)} -> {self.destination}")
        else:
            print(f"[{car_type_name} {self.id}] Faixa: {turn_name} | Rota direta: {self.entry_point} -> {self.destination}")

        # State flags - EXACTLY like Car
        self.is_car_stopped = False
        self.car_is_turning = False
        self.car_at_traffic_light = False
        self.is_turning = (False, '')
        self.is_switching_lane = (False, '')
        self.turning_ticks = 0
        self.turning_rotation_done = 0
        self.stopped_at_tl_id = False
        self.stopped_at_tl_start_time = False

        # Load sprite - use center for accurate lane positioning
        self.image = pygame.image.load(self.car_type[self.get_next_animation_index()]).convert_alpha()
        self.rect = self.image.get_rect(center=spawn_pos)

        # Start moving
        self.fires_car(speed=1)

    def _calculate_route(self):
        """Calculate route using A* algorithm - same as Car."""
        if self.entry_point not in self.network.entry_points:
            return []
        
        _, _, start_node = self.network.entry_points[self.entry_point]
        
        if self.destination not in self.network.exit_points:
            return []
            
        _, _, end_node = self.network.exit_points[self.destination]
        
        return self.pathfinder.find_path(start_node, end_node) or []

    def _get_time_multiplier(self):
        """Get time multiplier - includes 50% speed bonus for emergency vehicles."""
        if Car.is_paused:
            return 0
        # Emergency vehicles are 50% faster than normal cars
        return min(Car.time_speed, 10) * self.EMERGENCY_SPEED_MULTIPLIER

    def _update_next_turn(self):
        """Update next turn direction based on route - uses same logic as Car."""
        if not self.route or self.current_route_index >= len(self.route):
            self.next_turn_direction = Directions.FORWARD
            return
        
        current_node_id = self.route[self.current_route_index]
        
        if self.current_route_index < len(self.route) - 1:
            # Turn to reach the next intersection
            next_node_id = self.route[self.current_route_index + 1]
            self.next_turn_direction = _calculate_turn_direction(
                current_node_id, next_node_id, self.angle, self.network, is_exit=False
            )
        else:
            # Last intersection - turn to reach the exit
            self.next_turn_direction = _calculate_turn_direction(
                current_node_id, self.destination, self.angle, self.network, is_exit=True
            )

    def advance_route(self):
        """Advance to next intersection in route - same as Car."""
        if self.current_route_index < len(self.route):
            current_intersection = self.route[self.current_route_index]
            self.passed_intersections.add(current_intersection)
            self.current_route_index += 1
            self._update_next_turn()

    def set_car_at_tl(self, flag=True):
        self.car_at_traffic_light = flag

    def get_car_position(self):
        return (self.rect.centerx, self.rect.centery, self.angle)

    def flag_car_is_turning(self, flag):
        """Called when turning state changes - same as Car."""
        if self.car_is_turning and not flag:
            # Advance route (which also updates next turn direction)
            self.advance_route()
        self.car_is_turning = flag

    def is_car_done(self):
        """Check if vehicle has left the map."""
        return (self.rect.x < -100 or self.rect.x > 1400 or 
                self.rect.y > 850 or self.rect.y < -100)

    def fires_car(self, speed=1):
        """Start moving - same as Car but 50% faster due to EMERGENCY_SPEED_MULTIPLIER."""
        self.is_car_stopped = False
        self.base_speed = speed
        self.car_speed = speed * self._get_time_multiplier()

    def stop_car(self):
        """Stop the car - same as Car."""
        self.is_car_stopped = True
        self.base_speed = 0
        self.car_speed = 0

    def go_forward(self):
        """Move forward - EXACTLY the same as Car."""
        if Car.is_paused:
            return
            
        # Normalize angle - same as Car
        if self.angle > 360:
            self.angle = self.angle - 360
        if self.angle < -360:
            self.angle = self.angle + 360

        effective_speed = self.base_speed * self._get_time_multiplier()
        radians = math.radians(self.angle)
        vertical = math.cos(radians) * effective_speed
        horizontal = math.sin(radians) * effective_speed

        self.rect.x -= horizontal
        self.rect.y -= vertical

    def get_next_position(self):
        effective_speed = self.base_speed * self._get_time_multiplier()
        radians = math.radians(self.angle)
        vertical = math.cos(radians) * effective_speed
        horizontal = math.sin(radians) * effective_speed
        return ((self.rect.x - horizontal), (self.rect.y - vertical))

    def activate_turning(self):
        """Start turning at intersection - same as Car."""
        if not self.car_is_turning:
            self.is_turning = (True, self.next_turn_direction)
            self.car_is_turning = True
            self.fires_car()
            # Pre-calculate the target lane position for the turn endpoint
            self._calculate_turn_target()

    def ending_turning(self):
        """End turning - same as Car."""
        self.is_turning = (False, '')
        # Target position was gradually applied during turn - just clean up
        self.turn_target_pos = None
        self.turn_start_pos = None
        self.rotation_start_pos = None
    
    def _calculate_turn_target(self):
        """Calculate where the car should end up after completing the turn.
        Uses the RoadMap for accurate lane positions."""
        road_map = get_road_map()
        
        # Save starting position for smooth interpolation
        self.turn_start_pos = (self.rect.centerx, self.rect.centery)
        
        future_turn = self._peek_turn_after_current()
        current_turn = self.is_turning[1] if self.is_turning[0] else self.next_turn_direction
        
        # Use RoadMap to get the target position
        target_x, target_y = road_map.get_target_lane_after_turn(
            self.angle, 
            current_turn, 
            future_turn,
            (self.rect.centerx, self.rect.centery)
        )
        
        self.turn_target_pos = (target_x, target_y)
    
    def _interpolate_to_target_lane(self):
        """Gradually move towards the target lane position during rotation."""
        if not hasattr(self, 'turn_target_pos') or self.turn_target_pos is None:
            return
        if not hasattr(self, 'rotation_start_pos') or self.rotation_start_pos is None:
            return
        
        # Calculate interpolation progress (0 to 1) based on rotation done
        progress = min(1.0, self.turning_rotation_done / 90.0)
        
        # Apply easing for smoother motion (ease-out for more natural arc)
        progress = 1 - (1 - progress) * (1 - progress)
        
        target_x, target_y = self.turn_target_pos
        start_x, start_y = self.rotation_start_pos
        
        # Interpolate position
        if target_x is not None and start_x is not None:
            self.rect.centerx = int(start_x + (target_x - start_x) * progress)
        if target_y is not None and start_y is not None:
            self.rect.centery = int(start_y + (target_y - start_y) * progress)
    
    def _peek_turn_after_current(self):
        """Look ahead to see what turn direction is needed AT the NEXT intersection.
        
        If we're at intersection A going to B, we need to know what turn to make at B to go to C.
        This determines which lane to be in when we arrive at B.
        """
        next_index = self.current_route_index + 1
        
        # Calculate the angle we'll have after completing the current turn
        angle_norm = self.angle % 360
        current_turn = self.is_turning[1] if self.is_turning[0] else self.next_turn_direction
        if current_turn == Directions.LEFT:
            new_angle = (angle_norm + 90) % 360
        elif current_turn == Directions.RIGHT:
            new_angle = (angle_norm - 90) % 360
        else:
            new_angle = angle_norm
        
        if not self.route:
            return Directions.FORWARD
        
        # If next_index is beyond the route, we're heading to the exit from the last intersection
        if next_index >= len(self.route):
            return Directions.FORWARD
        
        # If next_index is at the last position in route, turn at that intersection leads to exit
        if next_index == len(self.route) - 1:
            next_intersection = self.route[next_index]
            return _calculate_turn_direction(
                next_intersection, self.destination, new_angle, self.network, is_exit=True
            )
        
        # Otherwise, calculate turn at next_index intersection to reach next_index + 1
        if next_index < len(self.route) - 1:
            intersection_at = self.route[next_index]
            going_to = self.route[next_index + 1]
            return _calculate_turn_direction(
                intersection_at, going_to, new_angle, self.network, is_exit=False
            )
        
        return Directions.FORWARD

    def handle_turning(self):
        """Handle turning logic - EXACTLY the same as Car."""
        if Car.is_paused:
            return
            
        if self.is_turning[1] == Directions.FORWARD:
            self.ending_turning()
            return

        time_mult = self._get_time_multiplier()
        self.turning_ticks += 0 if self.base_speed == 0 else time_mult

        if self.is_turning[1] == Directions.RIGHT:
            self.turn_right()
        elif self.is_turning[1] == Directions.LEFT:
            self.turn_left()

    def turn_left(self):
        """Turn left - with smooth lane interpolation."""
        time_mult = self._get_time_multiplier()
        
        # Phase 1: Move forward into intersection (longer for left turns)
        if self.turning_ticks < 70:
            self.go_forward()
            return

        # Phase 2: Brief pause before rotation
        if 70 <= self.turning_ticks < 72:
            self.stop_car()
            if not hasattr(self, 'rotation_start_pos') or self.rotation_start_pos is None:
                self.rotation_start_pos = (self.rect.centerx, self.rect.centery)
            return

        # Phase 3: Rotation with lane interpolation
        if self.turning_rotation_done < 90:
            rotation_step = min(4 * time_mult, 90 - self.turning_rotation_done)
            self.angle += rotation_step
            self.turning_rotation_done += rotation_step
            
            self._interpolate_to_target_lane()
            self.draw()

        # Phase 4: Complete turn
        if self.turning_rotation_done >= 90:
            self.ending_turning()
            self.fires_car()
            self.go_forward()
            self.turning_rotation_done = 0
            self.turning_ticks = 0
            self.rotation_start_pos = None

    def turn_right(self):
        """Turn right - with smooth lane interpolation."""
        time_mult = self._get_time_multiplier()
        
        # Phase 1: Move forward into intersection (shorter for right turns)
        if self.turning_ticks < 35:
            self.go_forward()
            return

        # Phase 2: Brief pause before rotation
        if 35 <= self.turning_ticks < 37:
            self.stop_car()
            if not hasattr(self, 'rotation_start_pos') or self.rotation_start_pos is None:
                self.rotation_start_pos = (self.rect.centerx, self.rect.centery)
            return

        # Phase 3: Rotation with lane interpolation
        if self.turning_rotation_done < 90:
            rotation_step = min(5 * time_mult, 90 - self.turning_rotation_done)
            self.angle -= rotation_step
            self.turning_rotation_done += rotation_step
            
            self._interpolate_to_target_lane()
            self.draw()

        # Phase 4: Complete turn
        if self.turning_rotation_done >= 90:
            self.ending_turning()
            self.fires_car()
            self.go_forward()
            self.turning_rotation_done = 0
            self.turning_ticks = 0
            self.rotation_start_pos = None

    def draw(self):
        """Draw the sprite - with siren animation."""
        self.image = pygame.image.load(self.car_type[self.get_next_animation_index()]).convert_alpha()
        rotated_image = pygame.transform.rotate(self.image, self.angle)
        self.rect = rotated_image.get_rect(center=self.rect.center)
        self.screen.blit(rotated_image, self.rect.topleft)

    def update(self):
        """Update method - only handles physics (turning, forward movement).
        Decision-making is handled by the agent."""
        if Car.is_paused:
            return

        if self.is_turning[0]:
            self.handle_turning()
        else:
            # Emergency vehicles just go forward, don't do lane switching
            self.go_forward()

    def get_next_animation_index(self):
        """Animate siren lights."""
        animation_frame = 20
        max_index = len(self.car_type) - 1

        if (animation_frame / self.animation_count) == 1:
            self.animation_index += 1
            if self.animation_index > max_index:
                self.animation_index = 0
            self.animation_count = 1
        else:
            self.animation_count += 1

        return self.animation_index
