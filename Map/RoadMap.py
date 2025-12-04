"""
Physical Road Map - Defines exact pixel positions of all lanes based on fundo.png

The background image (1280x720) has:
- 3 vertical roads (columns)
- 2 horizontal roads (rows)
- Each road has 6 lanes (3 per direction)
- Each lane is approximately 22-24 pixels wide

Lane order (from center line outward):
- Lane 1: Turn left (innermost, closest to center)
- Lane 2: Go straight (middle)
- Lane 3: Turn right (outermost, closest to edge)
"""

from enum import Enum
from typing import Dict, Tuple, Optional, List
from Models.Directions import Directions


class Direction(Enum):
    """Traffic flow direction."""
    UP = "up"        # South to North (angle 0)
    DOWN = "down"    # North to South (angle 180)
    LEFT = "left"    # East to West (angle 90)
    RIGHT = "right"  # West to East (angle -90)


class LaneType(Enum):
    """Type of lane based on allowed turn."""
    LEFT_TURN = "left_turn"
    STRAIGHT = "straight"
    RIGHT_TURN = "right_turn"


class Lane:
    """Represents a single lane on the road."""
    
    def __init__(self, lane_id: str, center: int, direction: Direction, 
                 lane_type: LaneType, road_id: str):
        self.id = lane_id
        self.center = center  # X for vertical roads, Y for horizontal
        self.direction = direction
        self.lane_type = lane_type
        self.road_id = road_id
    
    def __repr__(self):
        return f"Lane({self.id}, center={self.center}, dir={self.direction.value}, type={self.lane_type.value})"


class VerticalRoad:
    """A vertical road with lanes going UP and DOWN."""
    
    def __init__(self, road_id: str, center_x: int, lane_positions: Dict[str, Dict[str, int]]):
        """
        Args:
            road_id: Identifier for this road (e.g., "left", "mid", "right")
            center_x: X coordinate of the center dividing line
            lane_positions: Dict with "up" and "down" keys, each containing lane offsets
        """
        self.id = road_id
        self.center_x = center_x
        self.lane_positions = lane_positions
        
        up_offsets = lane_positions["up"]
        down_offsets = lane_positions["down"]
        
        # Create lanes for UP direction (right side of center, positive offset)
        self.lanes_up = {
            LaneType.LEFT_TURN: Lane(
                f"{road_id}_up_left",
                center_x + up_offsets["left_turn"],
                Direction.UP, LaneType.LEFT_TURN, road_id
            ),
            LaneType.STRAIGHT: Lane(
                f"{road_id}_up_straight",
                center_x + up_offsets["straight"],
                Direction.UP, LaneType.STRAIGHT, road_id
            ),
            LaneType.RIGHT_TURN: Lane(
                f"{road_id}_up_right",
                center_x + up_offsets["right_turn"],
                Direction.UP, LaneType.RIGHT_TURN, road_id
            ),
        }
        
        # Create lanes for DOWN direction (left side of center, negative offset)
        self.lanes_down = {
            LaneType.LEFT_TURN: Lane(
                f"{road_id}_down_left",
                center_x - down_offsets["left_turn"],
                Direction.DOWN, LaneType.LEFT_TURN, road_id
            ),
            LaneType.STRAIGHT: Lane(
                f"{road_id}_down_straight",
                center_x - down_offsets["straight"],
                Direction.DOWN, LaneType.STRAIGHT, road_id
            ),
            LaneType.RIGHT_TURN: Lane(
                f"{road_id}_down_right",
                center_x - down_offsets["right_turn"],
                Direction.DOWN, LaneType.RIGHT_TURN, road_id
            ),
        }
    
    def get_lane(self, direction: Direction, lane_type: LaneType) -> Lane:
        if direction == Direction.UP:
            return self.lanes_up[lane_type]
        else:
            return self.lanes_down[lane_type]
    
    def get_lane_x(self, direction: Direction, lane_type: LaneType) -> int:
        return self.get_lane(direction, lane_type).center


class HorizontalRoad:
    """A horizontal road with lanes going LEFT and RIGHT."""
    
    def __init__(self, road_id: str, center_y: int, lane_positions: Dict[str, Dict[str, int]]):
        """
        Args:
            road_id: Identifier for this road (e.g., "top", "bottom")
            center_y: Y coordinate of the center dividing line
            lane_positions: Dict with "right" and "left" keys, each containing lane offsets
        """
        self.id = road_id
        self.center_y = center_y
        self.lane_positions = lane_positions
        
        right_offsets = lane_positions["right"]
        left_offsets = lane_positions["left"]
        
        # Create lanes for RIGHT direction (below center, positive offset)
        self.lanes_right = {
            LaneType.LEFT_TURN: Lane(
                f"{road_id}_right_left",
                center_y + right_offsets["left_turn"],
                Direction.RIGHT, LaneType.LEFT_TURN, road_id
            ),
            LaneType.STRAIGHT: Lane(
                f"{road_id}_right_straight",
                center_y + right_offsets["straight"],
                Direction.RIGHT, LaneType.STRAIGHT, road_id
            ),
            LaneType.RIGHT_TURN: Lane(
                f"{road_id}_right_right",
                center_y + right_offsets["right_turn"],
                Direction.RIGHT, LaneType.RIGHT_TURN, road_id
            ),
        }
        
        # Create lanes for LEFT direction (above center, negative offset)
        self.lanes_left = {
            LaneType.LEFT_TURN: Lane(
                f"{road_id}_left_left",
                center_y - left_offsets["left_turn"],
                Direction.LEFT, LaneType.LEFT_TURN, road_id
            ),
            LaneType.STRAIGHT: Lane(
                f"{road_id}_left_straight",
                center_y - left_offsets["straight"],
                Direction.LEFT, LaneType.STRAIGHT, road_id
            ),
            LaneType.RIGHT_TURN: Lane(
                f"{road_id}_left_right",
                center_y - left_offsets["right_turn"],
                Direction.LEFT, LaneType.RIGHT_TURN, road_id
            ),
        }
    
    def get_lane(self, direction: Direction, lane_type: LaneType) -> Lane:
        if direction == Direction.RIGHT:
            return self.lanes_right[lane_type]
        else:
            return self.lanes_left[lane_type]
    
    def get_lane_y(self, direction: Direction, lane_type: LaneType) -> int:
        return self.get_lane(direction, lane_type).center


class RoadMap:
    """
    Physical road map with exact pixel positions measured from fundo.png.
    
    Provides accurate lane positions for all vehicles.
    """
    
    # ===== MEASURED FROM BACKGROUND IMAGE =====
    # These values are measured from fundo.png (1280x720)
    # Each road may have slightly different positions due to image compression
    
    # Center lines of vertical roads (X coordinates)
    VERTICAL_ROAD_CENTERS = {
        "left": 279,
        "mid": 638,
        "right": 1003
    }
    
    # Center lines of horizontal roads (Y coordinates)
    HORIZONTAL_ROAD_CENTERS = {
        "top": 185,
        "bottom": 535
    }
    
    # Lane offsets for each VERTICAL road, per direction
    # Format: {road_id: {"up": {...}, "down": {...}}}
    # UP = going north (right side of center, positive X offset)
    # DOWN = going south (left side of center, negative X offset)
    VERTICAL_LANE_OFFSETS = {
        "left": {
            "up": {"left_turn": 10, "straight": 31, "right_turn": 52},
            "down": {"left_turn": 13, "straight": 35, "right_turn": 57},
        },
        "mid": {
            "up": {"left_turn": 10, "straight": 31, "right_turn": 52},
            "down": {"left_turn": 13, "straight": 35, "right_turn": 57},
        },
        "right": {
            "up": {"left_turn": 10, "straight": 31, "right_turn": 52},
            "down": {"left_turn": 13, "straight": 35, "right_turn": 57},
        },
    }
    
    # Lane offsets for each HORIZONTAL road, per direction
    # RIGHT = going east (below center, positive Y offset)
    # LEFT = going west (above center, negative Y offset)
    HORIZONTAL_LANE_OFFSETS = {
        "top": {
            "right": {"left_turn": 10, "straight": 32, "right_turn": 53},
            "left": {"left_turn": 12, "straight": 35, "right_turn": 55},
        },
        "bottom": {
            "right": {"left_turn": 10, "straight": 32, "right_turn": 53},
            "left": {"left_turn": 12, "straight": 35, "right_turn": 55},
        },
    }
    
    def __init__(self):
        """Initialize the road map with all roads and lanes."""
        
        # Create vertical roads with per-road offsets
        self.vertical_roads = {
            "left": VerticalRoad("left", self.VERTICAL_ROAD_CENTERS["left"], self.VERTICAL_LANE_OFFSETS["left"]),
            "mid": VerticalRoad("mid", self.VERTICAL_ROAD_CENTERS["mid"], self.VERTICAL_LANE_OFFSETS["mid"]),
            "right": VerticalRoad("right", self.VERTICAL_ROAD_CENTERS["right"], self.VERTICAL_LANE_OFFSETS["right"]),
        }
        
        # Create horizontal roads with per-road offsets
        self.horizontal_roads = {
            "top": HorizontalRoad("top", self.HORIZONTAL_ROAD_CENTERS["top"], self.HORIZONTAL_LANE_OFFSETS["top"]),
            "bottom": HorizontalRoad("bottom", self.HORIZONTAL_ROAD_CENTERS["bottom"], self.HORIZONTAL_LANE_OFFSETS["bottom"]),
        }
        
        # Pre-calculate all lane positions for quick lookup
        self._build_lane_lookup()
    
    def _build_lane_lookup(self):
        """Build lookup tables for quick lane position queries."""
        self.all_lanes = {}
        
        for road in self.vertical_roads.values():
            for lane in road.lanes_up.values():
                self.all_lanes[lane.id] = lane
            for lane in road.lanes_down.values():
                self.all_lanes[lane.id] = lane
        
        for road in self.horizontal_roads.values():
            for lane in road.lanes_right.values():
                self.all_lanes[lane.id] = lane
            for lane in road.lanes_left.values():
                self.all_lanes[lane.id] = lane
    
    def get_lane_position_x(self, road_id: str, direction: Direction, lane_type: LaneType) -> int:
        """Get X position for a lane on a vertical road."""
        if road_id in self.vertical_roads:
            return self.vertical_roads[road_id].get_lane_x(direction, lane_type)
        raise ValueError(f"Unknown vertical road: {road_id}")
    
    def get_lane_position_y(self, road_id: str, direction: Direction, lane_type: LaneType) -> int:
        """Get Y position for a lane on a horizontal road."""
        if road_id in self.horizontal_roads:
            return self.horizontal_roads[road_id].get_lane_y(direction, lane_type)
        raise ValueError(f"Unknown horizontal road: {road_id}")
    
    def get_spawn_position(self, entry_point: str, turn_direction: Directions) -> Tuple[int, int, int]:
        """
        Get the spawn position for a car based on entry point and intended turn.
        
        Args:
            entry_point: Entry point ID (e.g., "south_left", "north_mid", "west_top", "east_bottom")
            turn_direction: The first turn direction (Directions.LEFT, RIGHT, or FORWARD)
        
        Returns:
            (x, y, angle) tuple for spawning the car
        """
        # Convert turn direction to lane type
        if turn_direction == Directions.LEFT:
            lane_type = LaneType.LEFT_TURN
        elif turn_direction == Directions.RIGHT:
            lane_type = LaneType.RIGHT_TURN
        else:
            lane_type = LaneType.STRAIGHT
        
        # Parse entry point
        parts = entry_point.split("_")
        entry_side = parts[0]  # south, north, west, east
        road_section = parts[1]  # left, mid, right, top, bottom
        
        if entry_side == "south":
            # Entering from south, going UP
            x = self.get_lane_position_x(road_section, Direction.UP, lane_type)
            return (x, 780, 0)
        
        elif entry_side == "north":
            # Entering from north, going DOWN
            x = self.get_lane_position_x(road_section, Direction.DOWN, lane_type)
            return (x, -50, 180)
        
        elif entry_side == "west":
            # Entering from west, going RIGHT
            y = self.get_lane_position_y(road_section, Direction.RIGHT, lane_type)
            return (-50, y, -90)
        
        elif entry_side == "east":
            # Entering from east, going LEFT
            y = self.get_lane_position_y(road_section, Direction.LEFT, lane_type)
            return (1340, y, 90)
        
        raise ValueError(f"Unknown entry point: {entry_point}")
    
    def get_lane_for_direction_and_turn(self, current_direction: Direction, 
                                         next_turn: Directions, road_id: str) -> int:
        """
        Get the lane position (X or Y) for a car based on its current direction and next turn.
        
        Args:
            current_direction: The direction the car is currently traveling
            next_turn: The next turn the car will make
            road_id: The road ID the car is on
        
        Returns:
            X position for vertical roads, Y position for horizontal roads
        """
        # Convert turn direction to lane type
        if next_turn == Directions.LEFT:
            lane_type = LaneType.LEFT_TURN
        elif next_turn == Directions.RIGHT:
            lane_type = LaneType.RIGHT_TURN
        else:
            lane_type = LaneType.STRAIGHT
        
        if current_direction in (Direction.UP, Direction.DOWN):
            return self.get_lane_position_x(road_id, current_direction, lane_type)
        else:
            return self.get_lane_position_y(road_id, current_direction, lane_type)
    
    def get_target_lane_after_turn(self, current_angle: float, turn_direction: Directions,
                                    next_turn_after: Directions, intersection_pos: Tuple[int, int]) -> Tuple[Optional[int], Optional[int]]:
        """
        Calculate the target lane position after completing a turn.
        
        Args:
            current_angle: Car's current angle before turning
            turn_direction: The turn being made now
            next_turn_after: The turn to make at the NEXT intersection
            intersection_pos: (x, y) of the intersection being crossed
        
        Returns:
            (target_x, target_y) - one will be None depending on the new direction
        """
        # Calculate new angle after turn
        if turn_direction == Directions.LEFT:
            new_angle = (current_angle + 90) % 360
        elif turn_direction == Directions.RIGHT:
            new_angle = (current_angle - 90) % 360
        else:
            new_angle = current_angle
        
        # Normalize angle
        if new_angle < 0:
            new_angle += 360
        
        # Determine new direction
        if 315 <= new_angle or new_angle < 45:
            new_direction = Direction.UP
        elif 45 <= new_angle < 135:
            new_direction = Direction.LEFT
        elif 135 <= new_angle < 225:
            new_direction = Direction.DOWN
        else:
            new_direction = Direction.RIGHT
        
        # Convert next turn to lane type
        if next_turn_after == Directions.LEFT:
            lane_type = LaneType.LEFT_TURN
        elif next_turn_after == Directions.RIGHT:
            lane_type = LaneType.RIGHT_TURN
        else:
            lane_type = LaneType.STRAIGHT
        
        # Find nearest road
        target_x = None
        target_y = None
        
        if new_direction in (Direction.UP, Direction.DOWN):
            # Will be on a vertical road - find nearest vertical road center
            nearest_road = min(self.VERTICAL_ROAD_CENTERS.items(),
                              key=lambda x: abs(x[1] - intersection_pos[0]))
            road_id = nearest_road[0]
            target_x = self.get_lane_position_x(road_id, new_direction, lane_type)
        else:
            # Will be on a horizontal road - find nearest horizontal road center
            nearest_road = min(self.HORIZONTAL_ROAD_CENTERS.items(),
                              key=lambda x: abs(x[1] - intersection_pos[1]))
            road_id = nearest_road[0]
            target_y = self.get_lane_position_y(road_id, new_direction, lane_type)
        
        return (target_x, target_y)
    
    def angle_to_direction(self, angle: float) -> Direction:
        """Convert an angle to a Direction enum."""
        angle_norm = angle % 360
        if angle_norm < 0:
            angle_norm += 360
        
        if 315 <= angle_norm or angle_norm < 45:
            return Direction.UP
        elif 45 <= angle_norm < 135:
            return Direction.LEFT
        elif 135 <= angle_norm < 225:
            return Direction.DOWN
        else:
            return Direction.RIGHT
    
    def get_current_lane_position(self, angle: float, position: Tuple[int, int], 
                                   next_turn: Directions) -> Tuple[Optional[int], Optional[int]]:
        """
        Get the correct lane position for a car based on its current angle and next turn.
        
        Returns (target_x, target_y) where one is None.
        """
        direction = self.angle_to_direction(angle)
        
        # Convert turn to lane type
        if next_turn == Directions.LEFT:
            lane_type = LaneType.LEFT_TURN
        elif next_turn == Directions.RIGHT:
            lane_type = LaneType.RIGHT_TURN
        else:
            lane_type = LaneType.STRAIGHT
        
        if direction in (Direction.UP, Direction.DOWN):
            # On vertical road
            nearest_road = min(self.VERTICAL_ROAD_CENTERS.items(),
                              key=lambda x: abs(x[1] - position[0]))
            road_id = nearest_road[0]
            target_x = self.get_lane_position_x(road_id, direction, lane_type)
            return (target_x, None)
        else:
            # On horizontal road
            nearest_road = min(self.HORIZONTAL_ROAD_CENTERS.items(),
                              key=lambda x: abs(x[1] - position[1]))
            road_id = nearest_road[0]
            target_y = self.get_lane_position_y(road_id, direction, lane_type)
            return (None, target_y)
    
    def print_all_lanes(self):
        """Debug: Print all lane positions."""
        print("\n=== VERTICAL ROADS (X positions) ===")
        for road_id, road in self.vertical_roads.items():
            print(f"\n{road_id.upper()} Road (center={road.center_x}):")
            print(f"  UP lanes (going north):")
            for lane_type, lane in road.lanes_up.items():
                print(f"    {lane_type.value}: x={lane.center}")
            print(f"  DOWN lanes (going south):")
            for lane_type, lane in road.lanes_down.items():
                print(f"    {lane_type.value}: x={lane.center}")
        
        print("\n=== HORIZONTAL ROADS (Y positions) ===")
        for road_id, road in self.horizontal_roads.items():
            print(f"\n{road_id.upper()} Road (center={road.center_y}):")
            print(f"  RIGHT lanes (going east):")
            for lane_type, lane in road.lanes_right.items():
                print(f"    {lane_type.value}: y={lane.center}")
            print(f"  LEFT lanes (going west):")
            for lane_type, lane in road.lanes_left.items():
                print(f"    {lane_type.value}: y={lane.center}")
    
    # Exact traffic light positions from main.py
    # Format: list of (x, y) positions for each traffic light
    # Each intersection has 4 sides with 3 traffic lights each
    TRAFFIC_LIGHT_POSITIONS = {
        "bottom_left": {
            "up": [(278, 621), (300, 621), (322, 621)],      # bottom_tl - controls UP traffic
            "down": [(256, 442), (234, 442), (212, 442)],    # top_tl - controls DOWN traffic
            "right": [(178, 542), (178, 564), (178, 586)],   # left_tl - controls RIGHT traffic
            "left": [(357, 519), (357, 497), (357, 475)],    # right_tl - controls LEFT traffic
        },
        "bottom_mid": {
            "up": [(637, 621), (659, 621), (681, 621)],
            "down": [(616, 442), (594, 442), (572, 442)],
            "right": [(537, 541), (537, 563), (537, 586)],
            "left": [(717, 519), (717, 497), (717, 474)],
        },
        "bottom_right": {
            "up": [(1002, 621), (1024, 621), (1046, 621)],
            "down": [(981, 442), (959, 442), (937, 442)],
            "right": [(902, 541), (902, 563), (902, 585)],
            "left": [(1082, 519), (1082, 497), (1082, 475)],
        },
        "top_left": {
            "up": [(278, 271), (300, 271), (322, 271)],
            "down": [(256, 92), (234, 92), (212, 92)],
            "right": [(178, 191), (178, 213), (178, 235)],
            "left": [(358, 169), (358, 147), (358, 125)],
        },
        "top_mid": {
            "up": [(637, 271), (659, 271), (681, 271)],
            "down": [(615, 92), (593, 92), (571, 92)],
            "right": [(537, 191), (537, 213), (537, 235)],
            "left": [(717, 169), (717, 147), (717, 125)],
        },
        "top_right": {
            "up": [(1002, 271), (1024, 271), (1046, 271)],
            "down": [(980, 92), (958, 92), (936, 92)],
            "right": [(902, 191), (902, 213), (902, 235)],
            "left": [(1082, 169), (1082, 147), (1082, 125)],
        },
    }
    
    def draw_debug_lanes(self, surface):
        """Draw lane positions on a pygame surface for debugging."""
        import pygame
        
        # Colors for different lane types
        colors = {
            LaneType.LEFT_TURN: (255, 100, 100),   # Red
            LaneType.STRAIGHT: (100, 255, 100),    # Green
            LaneType.RIGHT_TURN: (100, 100, 255),  # Blue
        }
        
        # Draw vertical road lanes
        for road_id, road in self.vertical_roads.items():
            # Draw center line
            pygame.draw.line(surface, (255, 255, 0), 
                           (road.center_x, 0), (road.center_x, 720), 1)
            
            # Draw UP lanes
            for lane_type, lane in road.lanes_up.items():
                color = colors[lane_type]
                # Draw lane line from top to bottom
                pygame.draw.line(surface, color,
                               (lane.center, 0), (lane.center, 720), 2)
                # Draw small markers every 100 pixels
                for y in range(50, 720, 100):
                    pygame.draw.circle(surface, color, (lane.center, y), 4)
            
            # Draw DOWN lanes
            for lane_type, lane in road.lanes_down.items():
                color = colors[lane_type]
                pygame.draw.line(surface, color,
                               (lane.center, 0), (lane.center, 720), 2)
                for y in range(50, 720, 100):
                    pygame.draw.circle(surface, color, (lane.center, y), 4)
        
        # Draw horizontal road lanes
        for road_id, road in self.horizontal_roads.items():
            # Draw center line
            pygame.draw.line(surface, (255, 255, 0),
                           (0, road.center_y), (1280, road.center_y), 1)
            
            # Draw RIGHT lanes
            for lane_type, lane in road.lanes_right.items():
                color = colors[lane_type]
                pygame.draw.line(surface, color,
                               (0, lane.center), (1280, lane.center), 2)
                for x in range(50, 1280, 100):
                    pygame.draw.circle(surface, color, (x, lane.center), 4)
            
            # Draw LEFT lanes
            for lane_type, lane in road.lanes_left.items():
                color = colors[lane_type]
                pygame.draw.line(surface, color,
                               (0, lane.center), (1280, lane.center), 2)
                for x in range(50, 1280, 100):
                    pygame.draw.circle(surface, color, (x, lane.center), 4)
        
        # Draw traffic light collision zones (magenta/pink rectangles)
        # Traffic light sprite is approximately 18x30 pixels
        # The rect is created at topleft position
        TL_WIDTH = 18
        TL_HEIGHT = 30
        stop_line_color = (255, 0, 255)  # Magenta
        
        for intersection_id, tl_positions in self.TRAFFIC_LIGHT_POSITIONS.items():
            for direction, positions in tl_positions.items():
                for (x, y) in positions:
                    # Draw rectangle at exact traffic light position
                    rect = pygame.Rect(x, y, TL_WIDTH, TL_HEIGHT)
                    pygame.draw.rect(surface, stop_line_color, rect, 2)
                    # Draw small cross at topleft corner
                    pygame.draw.line(surface, (255, 255, 255), (x-3, y), (x+3, y), 1)
                    pygame.draw.line(surface, (255, 255, 255), (x, y-3), (x, y+3), 1)


# Global instance for easy access
_road_map_instance: Optional[RoadMap] = None

def get_road_map() -> RoadMap:
    """Get the singleton RoadMap instance."""
    global _road_map_instance
    if _road_map_instance is None:
        _road_map_instance = RoadMap()
    return _road_map_instance


# Test function
if __name__ == "__main__":
    road_map = get_road_map()
    road_map.print_all_lanes()
    
    print("\n=== SPAWN POSITIONS ===")
    from Models.Directions import Directions
    
    test_entries = ["south_left", "south_mid", "north_right", "west_top", "east_bottom"]
    test_turns = [Directions.LEFT, Directions.FORWARD, Directions.RIGHT]
    
    for entry in test_entries:
        for turn in test_turns:
            pos = road_map.get_spawn_position(entry, turn)
            print(f"  {entry} + {turn.value}: pos={pos}")

