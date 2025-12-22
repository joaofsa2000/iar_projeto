# Map/Car.py

import math
import random
import pygame
from Models.Directions import Directions
from Models.PathFinding import get_traffic_network, get_pathfinder, get_random_destination, recalculate_route_avoiding_blocked, route_requires_blocked_intersection
from Map.RoadMap import get_road_map, Direction, LaneType

# imagens disponíveis para os veículos
RED_CAR = 'Map/Resources/Cars/carro-vermelho.png'
BLUE_CAR = 'Map/Resources/Cars/carro-azul.png'
GREEN_CAR = 'Map/Resources/Cars/carro-verde.png'
YELLOW_CAR = 'Map/Resources/Cars/carro-amarelo.png'

directions_options = [Directions.RIGHT, Directions.LEFT, Directions.FORWARD]

# Get road map singleton for accurate lane positions
def get_lane_position(entry_id, turn_direction, road_section=None):
    """Calculate the spawn position based on entry point and intended turn direction.
    Uses the RoadMap for accurate pixel positions.
    
    Args:
        entry_id: The entry point identifier (e.g., "south_left")
        turn_direction: The first turn direction (Directions.LEFT, RIGHT, or FORWARD)
        road_section: Ignored - extracted from entry_id
    
    Returns:
        (x, y) position for spawning
    """
    road_map = get_road_map()
    x, y, _ = road_map.get_spawn_position(entry_id, turn_direction)
    return (x, y)


# Legacy spawning_points for compatibility - uses middle lane by default
# These are now generated from RoadMap
def _generate_spawning_points():
    road_map = get_road_map()
    points = []
    
    entries = [
        ("south_left", 0), ("south_mid", 0), ("south_right", 0),
        ("north_left", 180), ("north_mid", 180), ("north_right", 180),
        ("west_top", -90), ("west_bottom", -90),
        ("east_top", 90), ("east_bottom", 90),
    ]
    
    for entry_id, angle in entries:
        x, y, _ = road_map.get_spawn_position(entry_id, Directions.FORWARD)
        points.append(((x, y), angle, entry_id))
    
    return points

spawning_points = _generate_spawning_points()

# Track recently used routes to avoid repetition
_recent_routes = []
_max_recent_routes = 15


def _get_road_section(entry_point):
    """Get the road section for an entry point."""
    if "left" in entry_point:
        return "left"
    elif "mid" in entry_point:
        return "mid"
    elif "right" in entry_point:
        return "right"
    elif "top" in entry_point:
        return "top"
    elif "bottom" in entry_point:
        return "bottom"
    return "mid"


def _get_angle_for_entry(entry_point):
    """Get the starting angle for an entry point."""
    if entry_point.startswith("south"):
        return 0  # Going up
    elif entry_point.startswith("north"):
        return 180  # Going down
    elif entry_point.startswith("west"):
        return -90  # Going right (270)
    elif entry_point.startswith("east"):
        return 90  # Going left
    return 0


def _calculate_turn_direction(current_node_id, next_target, current_angle, network, is_exit=False):
    """
    Calculate the turn direction to reach the next target from current node.
    
    Args:
        current_node_id: ID of the current intersection
        next_target: Either another intersection ID or an exit point ID
        current_angle: Current angle of the car
        network: The traffic network
        is_exit: Whether next_target is an exit point
    
    Returns:
        Directions.LEFT, Directions.RIGHT, or Directions.FORWARD
    """
    if current_node_id not in network.nodes:
        return Directions.FORWARD
    
    current_node = network.nodes[current_node_id]
    
    # Get target position
    if is_exit and next_target in network.exit_points:
        target_pos, _, _ = network.exit_points[next_target]
    elif not is_exit and next_target in network.nodes:
        target_pos = network.nodes[next_target].position
    else:
        return Directions.FORWARD
    
    # Calculate direction to target
    dx = target_pos[0] - current_node.position[0]
    dy = target_pos[1] - current_node.position[1]
    
    # Determine target angle
    if abs(dx) > abs(dy):
        target_angle = 270 if dx > 0 else 90  # 270 = right/east, 90 = left/west
    else:
        target_angle = 0 if dy < 0 else 180  # 0 = up/north, 180 = down/south
    
    # Normalize current angle
    current_normalized = current_angle % 360
    if current_normalized < 0:
        current_normalized += 360
    
    # Calculate turn direction
    diff = (target_angle - current_normalized + 360) % 360
    
    if diff == 0:
        return Directions.FORWARD
    elif diff == 90:
        return Directions.LEFT
    elif diff == 270:
        return Directions.RIGHT
    elif diff == 180:
        # U-turn - shouldn't happen with good pathfinding
        return Directions.FORWARD
    
    # Fallback
    return Directions.LEFT if diff < 180 else Directions.RIGHT


def _get_first_turn_for_route(entry_point, route, destination, angle, network):
    """
    Calculate the first ACTUAL turn direction a car will make based on its route.
    This determines which lane the car should spawn in.
    
    The car needs to be in the correct lane for its first TURN (LEFT or RIGHT),
    not just what happens at the first intersection (which might be FORWARD).
    
    Args:
        entry_point: Where the car enters (e.g., "south_left")
        route: List of intersection IDs the car will pass through
        destination: Exit point ID where car will leave
        angle: Starting angle of the car
        network: The traffic network
    
    Returns:
        Directions.LEFT, Directions.RIGHT, or Directions.FORWARD
    """
    if not route:
        return Directions.FORWARD
    
    # Track the angle as we traverse the route
    current_angle = angle
    
    # Check each intersection to find the first actual turn (LEFT or RIGHT)
    for i in range(len(route)):
        current_intersection = route[i]
        
        # Determine next target
        if i < len(route) - 1:
            # Next target is another intersection
            next_target = route[i + 1]
            is_exit = False
        else:
            # Next target is the exit
            next_target = destination
            is_exit = True
        
        # Calculate what turn happens at this intersection
        turn = _calculate_turn_direction(current_intersection, next_target, current_angle, network, is_exit)
        
        # If this is an actual turn (not FORWARD), use this lane
        if turn != Directions.FORWARD:
            return turn
        
        # If going forward, the angle stays the same - continue to next intersection
        # (no angle update needed since we're going straight)
    
    # If all turns are FORWARD, stay in the straight lane
    return Directions.FORWARD


def _get_unique_route():
    """Get a spawn point and destination with lane selection based on first turn."""
    global _recent_routes
    
    network = get_traffic_network()
    pathfinder = get_pathfinder()
    
    # List of all entry points
    entry_points_list = ["south_left", "south_mid", "south_right",
                         "north_left", "north_mid", "north_right",
                         "west_top", "west_bottom",
                         "east_top", "east_bottom"]
    
    # Try to find a unique route
    max_attempts = 20
    for attempt in range(max_attempts):
        entry_point = random.choice(entry_points_list)
        destination = get_random_destination(entry_point)
        
        # Create route key
        route_key = f"{entry_point}_{destination}"
        
        # Check if this route was used recently
        if route_key not in _recent_routes:
            # Calculate actual path
            if entry_point in network.entry_points:
                _, _, start_node = network.entry_points[entry_point]
                if destination in network.exit_points:
                    _, _, end_node = network.exit_points[destination]
                    route = pathfinder.find_path(start_node, end_node)
                    
                    if route:
                        # Determine the first turn direction using consistent logic
                        angle = _get_angle_for_entry(entry_point)
                        first_turn = _get_first_turn_for_route(entry_point, route, destination, angle, network)
                        
                        # Get the road section
                        road_section = _get_road_section(entry_point)
                        
                        # Calculate spawn position for the appropriate lane
                        spawn_pos = get_lane_position(entry_point, first_turn, road_section)
                        
                        # DEBUG: Print lane selection
                        lane_names = {Directions.LEFT: "ESQ", Directions.RIGHT: "DIR", Directions.FORWARD: "FRENTE"}
                        print(f"[SPAWN] {entry_point} -> {destination} | 1ª Viragem: {lane_names.get(first_turn, '?')} | Pos: {spawn_pos}")
                        
                        # Create spawn tuple: (position, angle, entry_id, first_turn)
                        spawn = (spawn_pos, angle, entry_point, first_turn)
                        
                        # Add to recent routes
                        _recent_routes.append(route_key)
                        if len(_recent_routes) > _max_recent_routes:
                            _recent_routes.pop(0)
                        
                        return spawn, destination, route
    
    # Fallback: use middle lane
    print("[SPAWN] FALLBACK - usando faixa do meio")
    entry_point = random.choice(entry_points_list)
    destination = get_random_destination(entry_point)
    angle = _get_angle_for_entry(entry_point)
    road_section = _get_road_section(entry_point)
    spawn_pos = get_lane_position(entry_point, Directions.FORWARD, road_section)
    spawn = (spawn_pos, angle, entry_point, Directions.FORWARD)
    
    if entry_point in network.entry_points:
        _, _, start_node = network.entry_points[entry_point]
        if destination in network.exit_points:
            _, _, end_node = network.exit_points[destination]
            route = pathfinder.find_path(start_node, end_node) or []
            return spawn, destination, route
    
    return spawn, destination, []


class Car(pygame.sprite.Sprite):
    # Class-level time multiplier - set by Environment
    time_speed = 1
    is_paused = False
    
    # Track all active car positions for collision avoidance
    active_cars = []
    
    @classmethod
    def set_time_speed(cls, speed, paused=False):
        """Set the global time speed for all cars."""
        cls.time_speed = max(1, speed)
        cls.is_paused = paused
    
    @classmethod
    def register_car(cls, car):
        """Register a car for collision tracking."""
        if car not in cls.active_cars:
            cls.active_cars.append(car)
    
    @classmethod
    def unregister_car(cls, car):
        """Unregister a car from collision tracking."""
        if car in cls.active_cars:
            cls.active_cars.remove(car)
    
    def __init__(self, screen, id):
        super().__init__()

        self.id = id
        self.contador = 0
        
        # Get unique route with lane-based spawn position
        spawning_point, self.destination, self.route = _get_unique_route()

        self.screen = screen
        self.base_speed = 1  # Velocidade base reduzida para tempo real mais realista
        self.car_speed = 0
        self.angle = spawning_point[1]
        self.entry_point = spawning_point[2]
        
        # A* Pathfinding attributes
        self.network = get_traffic_network()
        self.pathfinder = get_pathfinder()
        self.current_route_index = 0
        
        # Use the pre-calculated first turn direction from spawn
        # This ensures the lane matches the turn
        self.next_turn_direction = spawning_point[3] if len(spawning_point) > 3 else Directions.FORWARD
        
        # Track which intersections we've passed through
        self.passed_intersections = set()
        
        # Debug: Print route with lane info
        lane_name = {Directions.LEFT: "ESQUERDA", Directions.RIGHT: "DIREITA", Directions.FORWARD: "FRENTE"}
        turn_name = lane_name.get(self.next_turn_direction, "FRENTE")
        if self.route:
            print(f"[CARRO {self.id}] Faixa: {turn_name} | Rota: {self.entry_point} -> {' -> '.join(self.route)} -> {self.destination}")
        else:
            print(f"[CARRO {self.id}] Faixa: {turn_name} | SEM ROTA - {self.entry_point} -> {self.destination}")

        self.car_is_turning = False
        self.car_at_traffic_light = False

        self.is_turning = (False, '')
        self.is_switching_lane = (False, '')

        self.turning_ticks = 0
        self.turning_rotation_done = 0

        # Select random car color
        self.image = pygame.image.load(random.choice([RED_CAR, BLUE_CAR, GREEN_CAR, YELLOW_CAR])).convert_alpha()
        # Use center for accurate positioning on lanes
        self.rect = self.image.get_rect(center=spawning_point[0])
        
        # Register for collision tracking
        Car.register_car(self)

        # Check if any intersections in our route are currently blocked
        self._check_route_for_blocked_intersections()

        self.fires_car()

        # Cars spawn in correct lane - no initial lane switching needed

        self.stopped_at_tl_id = False
        self.stopped_at_tl_start_time = False
        
        # For collision avoidance and deadlock resolution
        self.waiting_for_car_ahead = False
        self.waiting_start_time = None  # When car started waiting
        self.yielding_to = None  # ID of car we're yielding to
        self.deadlock_check_counter = 0  # Counter to check deadlock periodically
        
        # For accident/blocked intersection handling
        self.waiting_for_accident = False  # Waiting at traffic light because no alternative route
        self.blocked_intersection_id = None  # Which intersection is blocking our route

    def __del__(self):
        """Cleanup when car is destroyed."""
        Car.unregister_car(self)

    def _get_time_multiplier(self):
        """Get the effective time multiplier for movement."""
        if Car.is_paused:
            return 0
        return min(Car.time_speed, 10)

    def _update_next_turn(self):
        """Update the next turn direction based on the route and current position.
        Uses the same calculation logic as lane selection for consistency."""
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
        """Move to the next intersection in the route."""
        if self.current_route_index < len(self.route):
            current_intersection = self.route[self.current_route_index]
            self.passed_intersections.add(current_intersection)
            self.current_route_index += 1
            self._update_next_turn()
    
    def handle_blocked_intersection(self, blocked_intersection_id):
        """Handle notification that an intersection is blocked (accident).
        
        If the car hasn't reached that intersection yet, try to recalculate route.
        If no alternative exists, mark car to wait at the traffic light before that intersection.
        """
        # Check if we're already at or past this intersection
        if blocked_intersection_id in self.passed_intersections:
            # Already passed it, no need to recalculate
            return
        
        # Check if our remaining route goes through this intersection
        remaining_route = self.route[self.current_route_index:]
        if blocked_intersection_id not in remaining_route:
            # Our route doesn't go through the blocked intersection
            return
        
        print(f"[CARRO {self.id}] A rota passa pelo cruzamento bloqueado {blocked_intersection_id}")
        
        # Determine current intersection (or the one we're heading to)
        if self.current_route_index < len(self.route):
            current_node = self.route[self.current_route_index]
        else:
            # Already at last intersection, can't recalculate
            return
        
        # Skip if current node IS the blocked one (we're already there)
        if current_node == blocked_intersection_id:
            print(f"[CARRO {self.id}] Já está no cruzamento bloqueado, a parar")
            self.waiting_for_accident = True
            self.blocked_intersection_id = blocked_intersection_id
            self.stop_car()
            return
        
        # Try to find alternative route
        new_route = recalculate_route_avoiding_blocked(current_node, self.destination)
        
        if new_route is not None and len(new_route) > 0:
            # Found alternative route!
            old_route = ' -> '.join(self.route[self.current_route_index:])
            new_route_str = ' -> '.join(new_route)
            print(f"[CARRO {self.id}] Nova rota encontrada: {new_route_str} (antes: {old_route})")
            
            # Update the route from current position
            self.route = self.route[:self.current_route_index] + new_route
            self._update_next_turn()
            self.waiting_for_accident = False
            self.blocked_intersection_id = None
        else:
            # No alternative route - must wait at traffic light until accident clears
            print(f"[CARRO {self.id}] Sem rota alternativa, vai esperar no semáforo")
            self.waiting_for_accident = True
            self.blocked_intersection_id = blocked_intersection_id
    
    def handle_intersection_cleared(self, intersection_id):
        """Handle notification that a previously blocked intersection is now clear."""
        # If this car was waiting for this intersection to clear, resume it
        if self.blocked_intersection_id == intersection_id:
            print(f"[CARRO {self.id}] Cruzamento {intersection_id} desbloqueado, a retomar rota")
            self.waiting_for_accident = False
            self.blocked_intersection_id = None
            self.fires_car()
        # Also check if car is currently waiting for any accident
        elif self.waiting_for_accident:
            # Check if the route is now clear
            if not self._is_route_blocked():
                print(f"[CARRO {self.id}] Rota agora livre após limpeza de {intersection_id}, a retomar")
                self.waiting_for_accident = False
                self.blocked_intersection_id = None
                self.fires_car()
    
    def clear_waiting_for_accident(self):
        """Clear the waiting for accident state (used when all disruptions are cleared)."""
        if self.waiting_for_accident:
            print(f"[CARRO {self.id}] Todas as perturbações limpas, a retomar")
            self.waiting_for_accident = False
            self.blocked_intersection_id = None
            self.fires_car()

    def is_at_blocked_intersection(self):
        """Check if the car is currently at a blocked intersection."""
        pathfinder = get_pathfinder()

        # Check if current intersection (next in route) is blocked
        if self.current_route_index < len(self.route):
            next_intersection = self.route[self.current_route_index]
            if pathfinder.is_intersection_blocked(next_intersection):
                return True

        return False

    def _is_route_blocked(self):
        """Check if any intersection in the remaining route is blocked."""
        pathfinder = get_pathfinder()

        # Check remaining route for blocked intersections
        for i in range(self.current_route_index, len(self.route)):
            intersection_id = self.route[i]
            if pathfinder.is_intersection_blocked(intersection_id):
                return True

        return False

    def _check_route_for_blocked_intersections(self):
        """Check if any intersections in the current route are blocked and try to recalculate."""
        if not self.route:
            return

        pathfinder = get_pathfinder()

        # Check remaining route for blocked intersections
        for i in range(self.current_route_index, len(self.route)):
            intersection_id = self.route[i]
            if pathfinder.is_intersection_blocked(intersection_id):
                # Found a blocked intersection - try to recalculate route
                self.handle_blocked_intersection(intersection_id)
                break  # Only handle one blocked intersection at a time

    def set_car_at_tl(self, flag=True):
        self.car_at_traffic_light = flag

    def get_car_position(self):
        return (self.rect.centerx, self.rect.centery, self.angle)

    def flag_car_is_turning(self, flag):
        if self.car_is_turning and not flag:
            # Advance route (which also updates next turn direction)
            self.advance_route()
        self.car_is_turning = flag

    def infinite_car(self):
        """Remove car when it leaves the map."""
        if self.rect.x < -100 or self.rect.x > 1400 or self.rect.y > 850 or self.rect.y < -100:
            Car.unregister_car(self)

    def fires_car(self, speed=1):
        self.base_speed = speed
        self.car_speed = speed * self._get_time_multiplier()

    def stop_car(self):
        self.base_speed = 0
        self.car_speed = 0

    def check_car_ahead(self):
        """Check if there's another car directly ahead in the SAME LANE.
        Cars in different lanes (side by side) should NOT block each other.
        Returns: (blocking_car, is_intersection_conflict) or (None, False)"""
        my_x, my_y, my_angle = self.get_car_position()
        
        # Normalize angle
        angle_norm = my_angle % 360
        if angle_norm < 0:
            angle_norm += 360
        
        min_distance = 55  # Minimum safe distance
        same_lane_tolerance = 15  # Strict tolerance - only cars in SAME lane
        
        for other_car in Car.active_cars:
            if other_car is self:
                continue
            
            # Skip if we're yielding to this car
            if self.yielding_to == other_car.id:
                continue
            
            other_x, other_y, other_angle = other_car.get_car_position()
            
            # Check if other car is going in a SIMILAR direction (same lane)
            # Cars going opposite directions are in different lanes
            other_angle_norm = other_angle % 360
            if other_angle_norm < 0:
                other_angle_norm += 360
            
            angle_diff = abs(angle_norm - other_angle_norm)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            
            # Only consider cars going in roughly the same direction (within 45 degrees)
            # This allows cars in opposite lanes to be side by side
            if angle_diff > 45:
                continue
            
            # Calculate distance
            dx = other_x - my_x
            dy = other_y - my_y
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance > min_distance or distance < 5:
                continue
            
            # Check if car is ahead based on our direction (strict same-lane check)
            is_ahead = False
            if 315 <= angle_norm or angle_norm < 45:  # Going up (north)
                is_ahead = dy < 0 and abs(dx) < same_lane_tolerance
            elif 45 <= angle_norm < 135:  # Going left (west)
                is_ahead = dx < 0 and abs(dy) < same_lane_tolerance
            elif 135 <= angle_norm < 225:  # Going down (south)
                is_ahead = dy > 0 and abs(dx) < same_lane_tolerance
            elif 225 <= angle_norm < 315:  # Going right (east)
                is_ahead = dx > 0 and abs(dy) < same_lane_tolerance
            
            if is_ahead:
                # Check if this is a potential deadlock (other car is also waiting)
                is_intersection_conflict = (
                    hasattr(other_car, 'waiting_for_car_ahead') and 
                    other_car.waiting_for_car_ahead and
                    distance < 45  # Very close - likely at intersection
                )
                return (other_car, is_intersection_conflict)
        
        return (None, False)
    
    def should_yield_to(self, other_car):
        """Determine if this car should yield to another car in a deadlock.
        Uses deterministic rules: lower ID yields to higher ID."""
        if other_car is None:
            return False
        
        # If other car is yielding to us, don't yield back
        if hasattr(other_car, 'yielding_to') and other_car.yielding_to == self.id:
            return False
        
        # Compare IDs - lower ID yields to higher ID
        try:
            my_id_num = int(''.join(filter(str.isdigit, str(self.id))) or '0')
            other_id_num = int(''.join(filter(str.isdigit, str(other_car.id))) or '0')
            return my_id_num < other_id_num
        except:
            # Fallback to string comparison
            return str(self.id) < str(other_car.id)
    
    def resolve_deadlock(self, blocking_car):
        """Resolve a deadlock situation by having one car yield."""
        if self.should_yield_to(blocking_car):
            # We should yield - stop and let the other car pass
            self.yielding_to = blocking_car.id
            self.stop_car()
            return True
        else:
            # Other car should yield - we can continue
            self.yielding_to = None
            return False

    def go_forward(self):
        if Car.is_paused:
            return
            
        if self.angle > 360: self.angle = 0 + self.angle - 360
        if self.angle < -360: self.angle = 0 + self.angle + 360

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
        if not self.car_is_turning:
            self.is_turning = (True, self.next_turn_direction)
            self.car_is_turning = True
            # Pre-calculate the target lane position for the turn endpoint
            self._calculate_turn_target()

    def ending_turning(self):
        self.is_turning = (False, '')
        # Target position was gradually applied during turn - just clean up
        self.turn_target_pos = None
        self.turn_start_pos = None
        self.rotation_start_pos = None
    
    def _calculate_turn_target(self):
        """Calculate where the car should end up after completing the turn.
        Uses the RoadMap for accurate lane positions.
        This accounts for the NEXT turn direction after this intersection."""
        
        road_map = get_road_map()
        
        # Save starting position for smooth interpolation
        self.turn_start_pos = (self.rect.centerx, self.rect.centery)
        
        # Look ahead: what turn comes after this one?
        future_turn = self._peek_turn_after_current()
        
        # Calculate the new heading after the current turn
        current_turn = self.is_turning[1] if self.is_turning[0] else self.next_turn_direction
        
        # Use RoadMap to get the target position
        target_x, target_y = road_map.get_target_lane_after_turn(
            self.angle, 
            current_turn, 
            future_turn,
            (self.rect.centerx, self.rect.centery)
        )
        
        self.turn_target_pos = (target_x, target_y)
    
    def _peek_turn_after_current(self):
        """Look ahead to see what turn direction is needed AT the NEXT intersection.
        
        If we're at intersection A going to B, we need to know what turn to make at B to go to C.
        This determines which lane to be in when we arrive at B.
        """
        # The car is currently turning at current_route_index
        # After the turn, it will go to current_route_index + 1
        # We need to know what turn happens at current_route_index + 1
        
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
            # We're at the last intersection, turning to exit
            # No more turns after this one
            return Directions.FORWARD
        
        # If next_index is at the last position in route, turn at that intersection leads to exit
        if next_index == len(self.route) - 1:
            # At next intersection (route[next_index]), we'll turn to reach destination
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

    def activate_switching_lane(self):
        self._update_next_turn()
        self.is_switching_lane = (True, self.next_turn_direction)

    def end_switching_lane(self):
        self.is_switching_lane = (False, '')

    def handle_turning(self):
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

    def turn_left(self):
        time_mult = self._get_time_multiplier()
        
        # Phase 1: Move forward into intersection (longer for left turns - wider arc)
        if self.turning_ticks < 70:
            self.go_forward()
            return

        # Phase 2: Brief pause before rotation
        if 70 <= self.turning_ticks < 72:
            self.stop_car()
            # Save position when rotation is about to start
            if not hasattr(self, 'rotation_start_pos') or self.rotation_start_pos is None:
                self.rotation_start_pos = (self.rect.centerx, self.rect.centery)
            return

        # Phase 3: Rotation with lane interpolation
        if self.turning_rotation_done < 90:
            rotation_step = min(4 * time_mult, 90 - self.turning_rotation_done)  # Slower rotation
            self.angle += rotation_step
            self.turning_rotation_done += rotation_step
            
            # Gradually interpolate towards target lane during rotation
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
        time_mult = self._get_time_multiplier()
        
        # Phase 1: Move forward into intersection (shorter for right turns - tighter arc)
        if self.turning_ticks < 35:
            self.go_forward()
            return

        # Phase 2: Brief pause before rotation
        if 35 <= self.turning_ticks < 37:
            self.stop_car()
            # Save position when rotation is about to start
            if not hasattr(self, 'rotation_start_pos') or self.rotation_start_pos is None:
                self.rotation_start_pos = (self.rect.centerx, self.rect.centery)
            return

        # Phase 3: Rotation with lane interpolation
        if self.turning_rotation_done < 90:
            rotation_step = min(5 * time_mult, 90 - self.turning_rotation_done)  # Slightly slower
            self.angle -= rotation_step
            self.turning_rotation_done += rotation_step
            
            # Gradually interpolate towards target lane during rotation
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

    def switch_lane(self, direction):
        """Lane switching is now handled only through turns at intersections.
        This method just continues forward movement."""
        if Car.is_paused:
            return
        
        # Simply end lane switching and continue forward
        self.end_switching_lane()
        self.fires_car()
        self.go_forward()

    def draw(self):
        rotated_image = pygame.transform.rotate(self.image, self.angle)
        self.rect = rotated_image.get_rect(center=self.rect.center)
        self.screen.blit(rotated_image, self.rect.topleft)

    def update(self):
        if Car.is_paused:
            return

        # Check for car ahead to avoid collision
        if not self.is_turning[0] and not self.is_switching_lane[0]:
            blocking_car, is_intersection_conflict = self.check_car_ahead()
            
            if blocking_car is not None:
                # There's a car ahead
                if is_intersection_conflict:
                    # Potential deadlock - check periodically for resolution
                    self.deadlock_check_counter += 1
                    
                    if self.deadlock_check_counter >= 30:  # Check every ~30 frames
                        self.deadlock_check_counter = 0
                        
                        # Try to resolve the deadlock
                        if self.resolve_deadlock(blocking_car):
                            # We're yielding - stay stopped
                            self.waiting_for_car_ahead = True
                            self.stop_car()
                            return
                        else:
                            # Other car should yield - we can try to move
                            self.waiting_for_car_ahead = False
                            self.yielding_to = None
                            self.fires_car()
                    else:
                        # Keep waiting while counter builds up
                        self.waiting_for_car_ahead = True
                        self.stop_car()
                        return
                else:
                    # Regular blocking - just wait
                    self.waiting_for_car_ahead = True
                    self.yielding_to = None
                    self.stop_car()
                    return
            else:
                # No car ahead - clear yielding state
                self.waiting_for_car_ahead = False
                self.yielding_to = None
                self.deadlock_check_counter = 0
            
        if self.is_turning[0]:
            self.handle_turning()
        elif self.is_switching_lane[0]:
            self.switch_lane(self.is_switching_lane[1])
        else:
            self.go_forward()

        self.infinite_car()
