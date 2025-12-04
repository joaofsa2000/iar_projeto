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
                     _get_road_section, _get_angle_for_entry, _calculate_turn_direction,
                     LANE_OFFSETS, ROAD_CENTERS_X, ROAD_CENTERS_Y)
from Models.PathFinding import get_traffic_network, get_pathfinder, get_random_destination

AMBULANCE = ['Map/Resources/Cars/ambulancia-1.png', 'Map/Resources/Cars/ambulancia-2.png']
POLICE = ['Map/Resources/Cars/policia-1.png', 'Map/Resources/Cars/policia-2.png']

# Entry points list
ENTRY_POINTS = ["south_left", "south_mid", "south_right",
                "north_left", "north_mid", "north_right",
                "west_top", "west_bottom",
                "east_top", "east_bottom"]


class EmergencyCar(pygame.sprite.Sprite):
    """Emergency vehicle that follows the same paths as regular cars but with priority."""
    
    def __init__(self, screen, id):
        super().__init__()

        self.animation_index = 0
        self.animation_count = 1
        self.car_type = random.choice([POLICE, AMBULANCE])

        self.id = id
        self.screen = screen
        self.base_speed = 2  # Same speed as regular cars for correct turning
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

        # Load sprite
        self.image = pygame.image.load(self.car_type[self.get_next_animation_index()]).convert_alpha()
        self.rect = self.image.get_rect(midtop=spawn_pos)
        
        # Start moving
        self.fires_car(speed=2)

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
        """Get time multiplier - same as Car."""
        if Car.is_paused:
            return 0
        return min(Car.time_speed, 10)

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

    def fires_car(self, speed=2):
        """Start moving - same as Car."""
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
        # Snap to target position calculated at turn start
        if hasattr(self, 'turn_target_pos') and self.turn_target_pos is not None:
            if self.turn_target_pos[0] is not None:
                self.rect.centerx = self.turn_target_pos[0]
            if self.turn_target_pos[1] is not None:
                self.rect.centery = self.turn_target_pos[1]
            self.turn_target_pos = None
    
    def _calculate_turn_target(self):
        """Calculate where the car should end up after completing the turn."""
        future_turn = self._peek_turn_after_current()
        
        if future_turn == Directions.LEFT:
            target_offset = LANE_OFFSETS["left_turn"]
        elif future_turn == Directions.RIGHT:
            target_offset = LANE_OFFSETS["right_turn"]
        else:
            target_offset = LANE_OFFSETS["straight"]
        
        angle_norm = self.angle % 360
        if angle_norm < 0:
            angle_norm += 360
        
        current_turn = self.is_turning[1] if self.is_turning[0] else self.next_turn_direction
        if current_turn == Directions.LEFT:
            new_angle = (angle_norm + 90) % 360
        elif current_turn == Directions.RIGHT:
            new_angle = (angle_norm - 90) % 360
        else:
            new_angle = angle_norm
        
        target_x = None
        target_y = None
        
        if 315 <= new_angle or new_angle < 45:
            road_centers = [ROAD_CENTERS_X["left"], ROAD_CENTERS_X["mid"], ROAD_CENTERS_X["right"]]
            nearest_center = min(road_centers, key=lambda c: abs(c - self.rect.centerx))
            target_x = nearest_center + target_offset
            
        elif 135 <= new_angle < 225:
            road_centers = [ROAD_CENTERS_X["left"], ROAD_CENTERS_X["mid"], ROAD_CENTERS_X["right"]]
            nearest_center = min(road_centers, key=lambda c: abs(c - self.rect.centerx))
            target_x = nearest_center - target_offset
            
        elif 45 <= new_angle < 135:
            road_centers = [ROAD_CENTERS_Y["top"], ROAD_CENTERS_Y["bottom"]]
            nearest_center = min(road_centers, key=lambda c: abs(c - self.rect.centery))
            target_y = nearest_center - target_offset
            
        elif 225 <= new_angle < 315:
            road_centers = [ROAD_CENTERS_Y["top"], ROAD_CENTERS_Y["bottom"]]
            nearest_center = min(road_centers, key=lambda c: abs(c - self.rect.centery))
            target_y = nearest_center + target_offset
        
        self.turn_target_pos = (target_x, target_y)
    
    def _peek_turn_after_current(self):
        """Look ahead to see what turn direction is needed after this intersection."""
        future_index = self.current_route_index + 1
        
        if not self.route or future_index >= len(self.route):
            if self.route and future_index - 1 < len(self.route):
                last_node = self.route[future_index - 1] if future_index - 1 >= 0 else None
                if last_node:
                    angle_norm = self.angle % 360
                    current_turn = self.is_turning[1] if self.is_turning[0] else self.next_turn_direction
                    if current_turn == Directions.LEFT:
                        new_angle = angle_norm + 90
                    elif current_turn == Directions.RIGHT:
                        new_angle = angle_norm - 90
                    else:
                        new_angle = angle_norm
                    
                    return _calculate_turn_direction(
                        last_node, self.destination, new_angle, self.network, is_exit=True
                    )
            return Directions.FORWARD
        
        current_node = self.route[future_index - 1] if future_index > 0 and future_index - 1 < len(self.route) else None
        next_node = self.route[future_index] if future_index < len(self.route) else None
        
        if current_node and next_node:
            angle_norm = self.angle % 360
            current_turn = self.is_turning[1] if self.is_turning[0] else self.next_turn_direction
            if current_turn == Directions.LEFT:
                new_angle = angle_norm + 90
            elif current_turn == Directions.RIGHT:
                new_angle = angle_norm - 90
            else:
                new_angle = angle_norm
            
            return _calculate_turn_direction(
                current_node, next_node, new_angle, self.network, is_exit=False
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
        """Turn left - EXACTLY the same as Car."""
        time_mult = self._get_time_multiplier()
        
        if self.turning_ticks < 58:
            self.go_forward()
            return

        if 58 <= self.turning_ticks < 60:
            self.stop_car()
            return

        if self.turning_rotation_done < 90:
            rotation_step = min(6 * time_mult, 90 - self.turning_rotation_done)
            self.angle += rotation_step
            self.turning_rotation_done += rotation_step
            self.fires_car()
            self.go_forward()
            self.stop_car()
            self.draw()

        if self.turning_rotation_done >= 90:
            self.ending_turning()
            self.fires_car()
            self.go_forward()
            self.turning_rotation_done = 0
            self.turning_ticks = 0

    def turn_right(self):
        """Turn right - EXACTLY the same as Car."""
        time_mult = self._get_time_multiplier()
        
        if self.turning_ticks < 25:
            self.go_forward()
            return

        if 25 <= self.turning_ticks < 27:
            self.stop_car()
            return

        if self.turning_rotation_done < 90:
            rotation_step = min(6 * time_mult, 90 - self.turning_rotation_done)
            self.angle -= rotation_step
            self.turning_rotation_done += rotation_step
            self.fires_car()
            self.go_forward()
            self.stop_car()
            self.draw()

        if self.turning_rotation_done >= 90:
            self.ending_turning()
            self.fires_car()
            self.go_forward()
            self.turning_rotation_done = 0
            self.turning_ticks = 0

    def draw(self):
        """Draw the sprite - with siren animation."""
        self.image = pygame.image.load(self.car_type[self.get_next_animation_index()]).convert_alpha()
        rotated_image = pygame.transform.rotate(self.image, self.angle)
        self.rect = rotated_image.get_rect(center=self.rect.center)
        self.screen.blit(rotated_image, self.rect.topleft)

    def update(self):
        """Update method - same structure as Car but no collision avoidance."""
        if Car.is_paused:
            return
            
        if self.is_turning[0]:
            self.handle_turning()
        else:
            # Emergency vehicles just go forward, don't do lane switching
            self.go_forward()

        # Check if car left the map
        if self.rect.x < -100 or self.rect.x > 1400 or self.rect.y > 850 or self.rect.y < -100:
            pass  # Will be handled by agent

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
