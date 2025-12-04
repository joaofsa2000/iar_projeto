# Models/PathFinding.py
"""
A* Pathfinding algorithm for car route calculation.
Defines the intersection graph and calculates optimal routes.
"""

import heapq
import math
import random
from enum import Enum
from typing import Dict, List, Tuple, Optional


class IntersectionNode:
    """Represents an intersection node in the traffic network."""
    
    def __init__(self, node_id: str, position: Tuple[int, int]):
        self.id = node_id
        self.position = position  # (x, y) center of intersection
        self.neighbors: Dict[str, 'IntersectionNode'] = {}  # {node_id: node}
        self.directions: Dict[str, str] = {}  # {node_id: direction_to_take}
    
    def add_neighbor(self, neighbor: 'IntersectionNode', direction: str):
        """Add a connected intersection with the direction to take."""
        self.neighbors[neighbor.id] = neighbor
        self.directions[neighbor.id] = direction
    
    def __lt__(self, other):
        return self.id < other.id


class TrafficNetwork:
    """
    Defines the traffic network as a graph of intersections.
    Based on the 6-intersection layout (2 rows x 3 columns).
    """
    
    def __init__(self):
        self.nodes: Dict[str, IntersectionNode] = {}
        self.entry_points: Dict[str, Tuple[Tuple[int, int], int, str]] = {}
        self.exit_points: Dict[str, Tuple[Tuple[int, int], int, str]] = {}
        self._build_network()
    
    def _build_network(self):
        """Build the intersection network based on the map layout."""
        # Create intersection nodes (center positions of each intersection)
        # Layout:
        #   top_left (268, 180)    top_mid (627, 180)    top_right (992, 180)
        #   bottom_left (268, 530) bottom_mid (627, 530) bottom_right (992, 530)
        
        # Intersection centers match road centers: X = {268, 627, 992}, Y = {178, 528}
        self.nodes = {
            "top_left": IntersectionNode("top_left", (268, 178)),
            "top_mid": IntersectionNode("top_mid", (627, 178)),
            "top_right": IntersectionNode("top_right", (992, 178)),
            "bottom_left": IntersectionNode("bottom_left", (268, 528)),
            "bottom_mid": IntersectionNode("bottom_mid", (627, 528)),
            "bottom_right": IntersectionNode("bottom_right", (992, 528)),
        }
        
        # Define ALL connections between intersections (bidirectional)
        # This allows cars to turn at any intersection
        
        # Horizontal connections (top row)
        self.nodes["top_left"].add_neighbor(self.nodes["top_mid"], "right")
        self.nodes["top_mid"].add_neighbor(self.nodes["top_left"], "left")
        self.nodes["top_mid"].add_neighbor(self.nodes["top_right"], "right")
        self.nodes["top_right"].add_neighbor(self.nodes["top_mid"], "left")
        
        # Horizontal connections (bottom row)
        self.nodes["bottom_left"].add_neighbor(self.nodes["bottom_mid"], "right")
        self.nodes["bottom_mid"].add_neighbor(self.nodes["bottom_left"], "left")
        self.nodes["bottom_mid"].add_neighbor(self.nodes["bottom_right"], "right")
        self.nodes["bottom_right"].add_neighbor(self.nodes["bottom_mid"], "left")
        
        # Vertical connections (left column)
        self.nodes["top_left"].add_neighbor(self.nodes["bottom_left"], "down")
        self.nodes["bottom_left"].add_neighbor(self.nodes["top_left"], "up")
        
        # Vertical connections (middle column)
        self.nodes["top_mid"].add_neighbor(self.nodes["bottom_mid"], "down")
        self.nodes["bottom_mid"].add_neighbor(self.nodes["top_mid"], "up")
        
        # Vertical connections (right column)
        self.nodes["top_right"].add_neighbor(self.nodes["bottom_right"], "down")
        self.nodes["bottom_right"].add_neighbor(self.nodes["top_right"], "up")
        
        # Define entry points (where cars spawn) and their nearest intersections
        # Positions are for the middle lane (straight) - actual spawn uses lane-based positioning
        # Road centers: left=268, mid=627, right=992
        # Horizontal road centers: top=178, bottom=528
        # Road centers: X = {left: 268, mid: 627, right: 992}, Y = {top: 178, bottom: 528}
        # Middle lane offset from center = 30 pixels (matching LANE_OFFSETS["straight"])
        
        self.entry_points = {
            # Bottom entry points (going UP, angle=0) - right side of road (center + 30)
            "south_left": ((298, 780), 0, "bottom_left"),    # 268 + 30
            "south_mid": ((657, 780), 0, "bottom_mid"),      # 627 + 30
            "south_right": ((1022, 780), 0, "bottom_right"), # 992 + 30
            # Top entry points (going DOWN, angle=180) - left side of road (center - 30)
            "north_left": ((238, -50), 180, "top_left"),     # 268 - 30
            "north_mid": ((597, -50), 180, "top_mid"),       # 627 - 30
            "north_right": ((962, -50), 180, "top_right"),   # 992 - 30
            # Left entry points (going RIGHT, angle=-90) - bottom side of road (center + 30)
            "west_top": ((-50, 208), -90, "top_left"),       # 178 + 30
            "west_bottom": ((-50, 558), -90, "bottom_left"), # 528 + 30
            # Right entry points (going LEFT, angle=90) - top side of road (center - 30)
            "east_top": ((1340, 148), 90, "top_right"),      # 178 - 30
            "east_bottom": ((1340, 498), 90, "bottom_right"),# 528 - 30
        }
        
        # Define exit points (where cars leave the map)
        # Exit positions are in the correct lane for that direction
        self.exit_points = {
            # Top exits (cars going UP exit north) - right side (center + 30)
            "north_left_exit": ((298, -50), 0, "top_left"),
            "north_mid_exit": ((657, -50), 0, "top_mid"),
            "north_right_exit": ((1022, -50), 0, "top_right"),
            # Bottom exits (cars going DOWN exit south) - left side (center - 30)
            "south_left_exit": ((238, 780), 180, "bottom_left"),
            "south_mid_exit": ((597, 780), 180, "bottom_mid"),
            "south_right_exit": ((962, 780), 180, "bottom_right"),
            # Left exits (cars going LEFT exit west) - top side (center - 30)
            "west_top_exit": ((-50, 148), 90, "top_left"),
            "west_bottom_exit": ((-50, 498), 90, "bottom_left"),
            # Right exits (cars going RIGHT exit east) - bottom side (center + 30)
            "east_top_exit": ((1340, 208), -90, "top_right"),
            "east_bottom_exit": ((1340, 558), -90, "bottom_right"),
        }
    
    def get_nearest_node(self, position: Tuple[int, int]) -> Optional[IntersectionNode]:
        """Find the nearest intersection node to a given position."""
        min_distance = float('inf')
        nearest = None
        
        for node in self.nodes.values():
            distance = self._euclidean_distance(position, node.position)
            if distance < min_distance:
                min_distance = distance
                nearest = node
        
        return nearest
    
    def _euclidean_distance(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        """Calculate Euclidean distance between two points."""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def _heuristic(self, node: IntersectionNode, goal: IntersectionNode) -> float:
        """A* heuristic: Euclidean distance to goal."""
        return self._euclidean_distance(node.position, goal.position)


class AStarPathfinder:
    """A* algorithm implementation for finding optimal routes."""
    
    def __init__(self, network: TrafficNetwork):
        self.network = network
    
    def find_path(self, start_id: str, goal_id: str) -> Optional[List[str]]:
        """
        Find the optimal path from start to goal using A*.
        """
        if start_id not in self.network.nodes or goal_id not in self.network.nodes:
            return None
        
        if start_id == goal_id:
            return [start_id]
        
        start = self.network.nodes[start_id]
        goal = self.network.nodes[goal_id]
        
        # Priority queue: (f_score, node_id)
        open_set = [(0, start_id)]
        heapq.heapify(open_set)
        
        came_from: Dict[str, str] = {}
        g_score: Dict[str, float] = {node_id: float('inf') for node_id in self.network.nodes}
        g_score[start_id] = 0
        
        f_score: Dict[str, float] = {node_id: float('inf') for node_id in self.network.nodes}
        f_score[start_id] = self.network._heuristic(start, goal)
        
        open_set_hash = {start_id}
        
        while open_set:
            _, current_id = heapq.heappop(open_set)
            open_set_hash.discard(current_id)
            
            if current_id == goal_id:
                return self._reconstruct_path(came_from, current_id)
            
            current = self.network.nodes[current_id]
            
            for neighbor_id, neighbor in current.neighbors.items():
                tentative_g = g_score[current_id] + self.network._euclidean_distance(
                    current.position, neighbor.position
                )
                
                if tentative_g < g_score[neighbor_id]:
                    came_from[neighbor_id] = current_id
                    g_score[neighbor_id] = tentative_g
                    f_score[neighbor_id] = tentative_g + self.network._heuristic(neighbor, goal)
                    
                    if neighbor_id not in open_set_hash:
                        heapq.heappush(open_set, (f_score[neighbor_id], neighbor_id))
                        open_set_hash.add(neighbor_id)
        
        return None
    
    def _reconstruct_path(self, came_from: Dict[str, str], current: str) -> List[str]:
        """Reconstruct the path from start to goal."""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path
    
    def get_direction_for_next_node(self, current_node_id: str, next_node_id: str, 
                                     current_angle: int) -> str:
        """
        Determine what direction the car should turn to reach the next node.
        
        Args:
            current_node_id: ID of current intersection
            next_node_id: ID of next intersection in path
            current_angle: Current angle of the car (0=up, 90=left, 180=down, -90=right)
        
        Returns:
            Direction to turn: "forward", "left", or "right"
        """
        if current_node_id not in self.network.nodes or next_node_id not in self.network.nodes:
            return "forward"
        
        current = self.network.nodes[current_node_id]
        next_node = self.network.nodes[next_node_id]
        
        # Calculate required direction based on positions
        dx = next_node.position[0] - current.position[0]
        dy = next_node.position[1] - current.position[1]
        
        # Determine target angle based on direction to next node
        # 0 = up (north), 90 = left (west), 180 = down (south), -90/270 = right (east)
        if abs(dx) > abs(dy):
            # Primarily horizontal movement
            target_angle = 270 if dx > 0 else 90  # 270/-90 = right (east), 90 = left (west)
        else:
            # Primarily vertical movement
            target_angle = 0 if dy < 0 else 180  # 0 = up (north), 180 = down (south)
        
        # Normalize current angle to 0-359
        current_normalized = current_angle % 360
        if current_normalized < 0:
            current_normalized += 360
        
        # Calculate the angle difference
        diff = (target_angle - current_normalized + 360) % 360
        
        if diff == 0:
            return "forward"
        elif diff == 90:
            return "left"
        elif diff == 270:
            return "right"
        elif diff == 180:
            # U-turn - pick randomly
            return random.choice(["left", "right"])
        
        # For other angles, determine closest turn
        if diff < 180:
            return "left"
        else:
            return "right"


# Global traffic network instance
_traffic_network = None
_pathfinder = None


def get_traffic_network() -> TrafficNetwork:
    """Get the singleton traffic network instance."""
    global _traffic_network
    if _traffic_network is None:
        _traffic_network = TrafficNetwork()
    return _traffic_network


def get_pathfinder() -> AStarPathfinder:
    """Get the singleton pathfinder instance."""
    global _pathfinder
    if _pathfinder is None:
        _pathfinder = AStarPathfinder(get_traffic_network())
    return _pathfinder


def calculate_route(start_entry: str, destination_exit: str) -> Optional[List[str]]:
    """
    Calculate a route from an entry point to an exit point.
    """
    network = get_traffic_network()
    pathfinder = get_pathfinder()
    
    if start_entry in network.entry_points:
        _, _, start_node = network.entry_points[start_entry]
    else:
        return None
    
    if destination_exit in network.exit_points:
        _, _, end_node = network.exit_points[destination_exit]
    else:
        return None
    
    return pathfinder.find_path(start_node, end_node)


def get_random_destination(entry_point: str) -> str:
    """
    Get a random valid destination exit point for a given entry.
    Prefers destinations that require turns (more interesting routes).
    """
    network = get_traffic_network()
    
    if entry_point not in network.entry_points:
        return random.choice(list(network.exit_points.keys()))
    
    _, _, start_node = network.entry_points[entry_point]
    
    # Categorize exits by how many turns they require
    straight_exits = []  # Same direction as entry
    turn_exits = []      # Require at least one turn
    
    # Determine entry direction
    entry_direction = entry_point.split("_")[0]  # south, north, west, east
    
    for exit_id, (_, _, exit_node) in network.exit_points.items():
        exit_direction = exit_id.split("_")[0]  # south, north, west, east
        
        # Straight through: entering from south exits north, etc.
        is_straight = (
            (entry_direction == "south" and exit_direction == "north") or
            (entry_direction == "north" and exit_direction == "south") or
            (entry_direction == "west" and exit_direction == "east") or
            (entry_direction == "east" and exit_direction == "west")
        )
        
        # Don't allow U-turns (exit same direction as entry)
        is_uturn = entry_direction == exit_direction
        
        if is_uturn:
            continue  # Skip U-turn exits
        elif is_straight:
            # Only add straight exits if they're not in the same lane
            if start_node != exit_node:
                straight_exits.append(exit_id)
        else:
            turn_exits.append(exit_id)
    
    # 70% chance to pick a turn exit, 30% straight (if available)
    if turn_exits and (not straight_exits or random.random() < 0.7):
        return random.choice(turn_exits)
    elif straight_exits:
        return random.choice(straight_exits)
    elif turn_exits:
        return random.choice(turn_exits)
    else:
        # Fallback
        return random.choice(list(network.exit_points.keys()))
