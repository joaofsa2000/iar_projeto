# Map/Car.py

import math
import random
import pygame
from Models.Directions import Directions
from Models.PathFinding import get_traffic_network, get_pathfinder, get_random_destination

# imagens disponíveis para os veículos
RED_CAR = 'Map/Resources/Cars/carro-vermelho.png'
BLUE_CAR = 'Map/Resources/Cars/carro-azul.png'
GREEN_CAR = 'Map/Resources/Cars/carro-verde.png'
YELLOW_CAR = 'Map/Resources/Cars/carro-amarelo.png'

directions_options = [Directions.RIGHT, Directions.LEFT, Directions.FORWARD]

# Road centers for each column/row (center line between opposing traffic)
# Measured from fundo.png - the center dividing line of each road
ROAD_CENTERS_X = {"left": 268, "mid": 627, "right": 992}
ROAD_CENTERS_Y = {"top": 178, "bottom": 528}

# Lane offsets from the road center (for 3 lanes per direction)
# Measured from the arrow positions in fundo.png:
# - Each direction has 3 lanes (left turn, straight, right turn)
# - Lane width ≈ 18 pixels each
# - Offsets are from center line to lane center
# For cars going UP: lanes are on RIGHT side of center (positive offset on X)
# For cars going DOWN: lanes are on LEFT side of center (negative offset on X)
# For cars going RIGHT: lanes are BELOW center (positive offset on Y)
# For cars going LEFT: lanes are ABOVE center (negative offset on Y)
LANE_OFFSETS = {
    "left_turn": 13,   # Innermost lane (closest to center line)
    "straight": 30,    # Middle lane
    "right_turn": 48,  # Outermost lane (closest to road edge)
}

# Base entry points - will be adjusted based on turn direction
# Format: (base_position, angle, entry_id, road_section)
base_entry_points = [
    # South entries (going up, angle=0)
    (780, 0, "south_left", "left"),
    (780, 0, "south_mid", "mid"),
    (780, 0, "south_right", "right"),
    
    # North entries (going down, angle=180)
    (-50, 180, "north_left", "left"),
    (-50, 180, "north_mid", "mid"),
    (-50, 180, "north_right", "right"),
    
    # West entries (going right, angle=-90)
    (-50, -90, "west_top", "top"),
    (-50, -90, "west_bottom", "bottom"),
    
    # East entries (going left, angle=90)
    (1340, 90, "east_top", "top"),
    (1340, 90, "east_bottom", "bottom"),
]


def get_lane_position(entry_id, turn_direction, road_section):
    """Calculate the spawn position based on entry point and intended turn direction.
    
    Args:
        entry_id: The entry point identifier (e.g., "south_left")
        turn_direction: The first turn direction (Directions.LEFT, RIGHT, or FORWARD)
        road_section: Which road section ("left", "mid", "right" for vertical, "top", "bottom" for horizontal)
    
    Returns:
        (x, y) position for spawning
    """
    # Determine lane offset based on turn direction
    if turn_direction == Directions.LEFT:
        lane_type = "left_turn"
    elif turn_direction == Directions.RIGHT:
        lane_type = "right_turn"
    else:
        lane_type = "straight"
    
    offset = LANE_OFFSETS[lane_type]
    
    # Calculate position based on entry type
    if entry_id.startswith("south"):
        # Going UP - lanes are on RIGHT side of road center (positive offset)
        center_x = ROAD_CENTERS_X[road_section]
        x = center_x + offset
        y = 780
    elif entry_id.startswith("north"):
        # Going DOWN - lanes are on LEFT side of road center (negative offset)
        center_x = ROAD_CENTERS_X[road_section]
        x = center_x - offset
        y = -50
    elif entry_id.startswith("west"):
        # Going RIGHT - lanes are below road center (positive offset for y)
        center_y = ROAD_CENTERS_Y[road_section]
        x = -50
        y = center_y + offset
    elif entry_id.startswith("east"):
        # Going LEFT - lanes are above road center (negative offset for y)
        center_y = ROAD_CENTERS_Y[road_section]
        x = 1340
        y = center_y - offset
    else:
        # Fallback
        x, y = 0, 0
    
    return (x, y)


# Legacy spawning_points for compatibility - uses middle lane by default
spawning_points = [
    # South entries (going up, angle=0) - middle lane
    ((ROAD_CENTERS_X["left"] + LANE_OFFSETS["straight"], 780), 0, "south_left"),
    ((ROAD_CENTERS_X["mid"] + LANE_OFFSETS["straight"], 780), 0, "south_mid"),
    ((ROAD_CENTERS_X["right"] + LANE_OFFSETS["straight"], 780), 0, "south_right"),
    
    # North entries (going down, angle=180) - middle lane
    ((ROAD_CENTERS_X["left"] - LANE_OFFSETS["straight"], -50), 180, "north_left"),
    ((ROAD_CENTERS_X["mid"] - LANE_OFFSETS["straight"], -50), 180, "north_mid"),
    ((ROAD_CENTERS_X["right"] - LANE_OFFSETS["straight"], -50), 180, "north_right"),
    
    # West entries (going right, angle=-90) - middle lane
    ((-50, ROAD_CENTERS_Y["top"] + LANE_OFFSETS["straight"]), -90, "west_top"),
    ((-50, ROAD_CENTERS_Y["bottom"] + LANE_OFFSETS["straight"]), -90, "west_bottom"),
    
    # East entries (going left, angle=90) - middle lane
    ((1340, ROAD_CENTERS_Y["top"] - LANE_OFFSETS["straight"]), 90, "east_top"),
    ((1340, ROAD_CENTERS_Y["bottom"] - LANE_OFFSETS["straight"]), 90, "east_bottom"),
]

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
    Calculate the first turn direction a car will make based on its route.
    This determines which lane the car should spawn in.
    
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
    
    first_intersection = route[0]
    
    # Determine what the car does at the first intersection
    if len(route) >= 2:
        # Route has multiple intersections - turn to get to the second one
        second_intersection = route[1]
        return _calculate_turn_direction(first_intersection, second_intersection, angle, network, is_exit=False)
    else:
        # Route has only one intersection - turn to reach the exit
        return _calculate_turn_direction(first_intersection, destination, angle, network, is_exit=True)


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
        self.base_speed = 2
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
        self.rect = self.image.get_rect(midtop=spawning_point[0])
        
        # Register for collision tracking
        Car.register_car(self)
        
        self.fires_car()

        # Cars spawn in correct lane - no initial lane switching needed

        self.stopped_at_tl_id = False
        self.stopped_at_tl_start_time = False
        
        # For collision avoidance and deadlock resolution
        self.waiting_for_car_ahead = False
        self.waiting_start_time = None  # When car started waiting
        self.yielding_to = None  # ID of car we're yielding to
        self.deadlock_check_counter = 0  # Counter to check deadlock periodically

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

    def fires_car(self, speed=2):
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
        # Snap to target position calculated at turn start
        if hasattr(self, 'turn_target_pos') and self.turn_target_pos is not None:
            if self.turn_target_pos[0] is not None:
                self.rect.centerx = self.turn_target_pos[0]
            if self.turn_target_pos[1] is not None:
                self.rect.centery = self.turn_target_pos[1]
            self.turn_target_pos = None
    
    def _calculate_turn_target(self):
        """Calculate where the car should end up after completing the turn.
        This accounts for the NEXT turn direction after this intersection."""
        
        # First update next turn direction for AFTER this turn completes
        # We need to look ahead: what turn comes after this one?
        future_turn = self._peek_turn_after_current()
        
        # Determine target lane offset based on future turn
        if future_turn == Directions.LEFT:
            target_offset = LANE_OFFSETS["left_turn"]
        elif future_turn == Directions.RIGHT:
            target_offset = LANE_OFFSETS["right_turn"]
        else:
            target_offset = LANE_OFFSETS["straight"]
        
        # Calculate the new heading after the current turn
        angle_norm = self.angle % 360
        if angle_norm < 0:
            angle_norm += 360
        
        # Determine new angle after turn
        current_turn = self.is_turning[1] if self.is_turning[0] else self.next_turn_direction
        if current_turn == Directions.LEFT:
            new_angle = (angle_norm + 90) % 360
        elif current_turn == Directions.RIGHT:
            new_angle = (angle_norm - 90) % 360
        else:
            new_angle = angle_norm
        
        # Calculate target position based on new heading
        target_x = None
        target_y = None
        
        if 315 <= new_angle or new_angle < 45:
            # Will be going UP - adjust X position
            road_centers = [ROAD_CENTERS_X["left"], ROAD_CENTERS_X["mid"], ROAD_CENTERS_X["right"]]
            nearest_center = min(road_centers, key=lambda c: abs(c - self.rect.centerx))
            target_x = nearest_center + target_offset
            
        elif 135 <= new_angle < 225:
            # Will be going DOWN - adjust X position
            road_centers = [ROAD_CENTERS_X["left"], ROAD_CENTERS_X["mid"], ROAD_CENTERS_X["right"]]
            nearest_center = min(road_centers, key=lambda c: abs(c - self.rect.centerx))
            target_x = nearest_center - target_offset
            
        elif 45 <= new_angle < 135:
            # Will be going LEFT - adjust Y position
            road_centers = [ROAD_CENTERS_Y["top"], ROAD_CENTERS_Y["bottom"]]
            nearest_center = min(road_centers, key=lambda c: abs(c - self.rect.centery))
            target_y = nearest_center - target_offset
            
        elif 225 <= new_angle < 315:
            # Will be going RIGHT - adjust Y position
            road_centers = [ROAD_CENTERS_Y["top"], ROAD_CENTERS_Y["bottom"]]
            nearest_center = min(road_centers, key=lambda c: abs(c - self.rect.centery))
            target_y = nearest_center + target_offset
        
        self.turn_target_pos = (target_x, target_y)
    
    def _peek_turn_after_current(self):
        """Look ahead to see what turn direction is needed after completing the current intersection."""
        # The car is about to turn at current_route_index
        # After the turn, current_route_index will be incremented
        # We need to know what turn comes AFTER that
        
        future_index = self.current_route_index + 1
        
        if not self.route or future_index >= len(self.route):
            # At or near end of route - check exit
            if self.route and future_index - 1 < len(self.route):
                last_node = self.route[future_index - 1] if future_index - 1 >= 0 else None
                if last_node:
                    # Calculate angle after current turn
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
            # Calculate angle after current turn
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

    def turn_left(self):
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
