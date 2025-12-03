# Models/PathFinding.py
"""
A* Pathfinding algorithm for car route calculation.
Defines the intersection graph and calculates optimal routes.
"""

import heapq
import math
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
        self.entry_points: Dict[str, Tuple[Tuple[int, int], int, str]] = {}  # {entry_id: (position, angle, nearest_node)}
        self.exit_points: Dict[str, Tuple[Tuple[int, int], int, str]] = {}  # {exit_id: (position, angle, nearest_node)}
        self._build_network()
    
    def _build_network(self):
        """Build the intersection network based on the map layout."""
        # Create intersection nodes (center positions of each intersection)
        # Layout:
        #   top_left (268, 180)    top_mid (627, 180)    top_right (992, 180)
        #   bottom_left (268, 530) bottom_mid (627, 530) bottom_right (992, 530)
        
        self.nodes = {
            "top_left": IntersectionNode("top_left", (268, 180)),
            "top_mid": IntersectionNode("top_mid", (627, 180)),
            "top_right": IntersectionNode("top_right", (992, 180)),
            "bottom_left": IntersectionNode("bottom_left", (268, 530)),
            "bottom_mid": IntersectionNode("bottom_mid", (627, 530)),
            "bottom_right": IntersectionNode("bottom_right", (992, 530)),
        }
        
        # Define connections between intersections
        # Each connection includes the direction the car must take to reach the neighbor
        
        # Horizontal connections (left-right)
        # Top row
        self.nodes["top_left"].add_neighbor(self.nodes["top_mid"], "forward")  # going right
        self.nodes["top_mid"].add_neighbor(self.nodes["top_left"], "forward")  # going left
        self.nodes["top_mid"].add_neighbor(self.nodes["top_right"], "forward")  # going right
        self.nodes["top_right"].add_neighbor(self.nodes["top_mid"], "forward")  # going left
        
        # Bottom row
        self.nodes["bottom_left"].add_neighbor(self.nodes["bottom_mid"], "forward")
        self.nodes["bottom_mid"].add_neighbor(self.nodes["bottom_left"], "forward")
        self.nodes["bottom_mid"].add_neighbor(self.nodes["bottom_right"], "forward")
        self.nodes["bottom_right"].add_neighbor(self.nodes["bottom_mid"], "forward")
        
        # Vertical connections (top-bottom)
        self.nodes["top_left"].add_neighbor(self.nodes["bottom_left"], "forward")
        self.nodes["bottom_left"].add_neighbor(self.nodes["top_left"], "forward")
        self.nodes["top_mid"].add_neighbor(self.nodes["bottom_mid"], "forward")
        self.nodes["bottom_mid"].add_neighbor(self.nodes["top_mid"], "forward")
        self.nodes["top_right"].add_neighbor(self.nodes["bottom_right"], "forward")
        self.nodes["bottom_right"].add_neighbor(self.nodes["top_right"], "forward")
        
        # Define entry points (where cars spawn) and their nearest intersections
        # Format: (position, angle, nearest_intersection_id)
        self.entry_points = {
            # Bottom entry points (going up, angle=0)
            "south_left": ((310, 780), 0, "bottom_left"),
            "south_mid": ((669, 780), 0, "bottom_mid"),
            "south_right": ((1034, 780), 0, "bottom_right"),
            # Top entry points (going down, angle=180)
            "north_left": ((244, -50), 180, "top_left"),
            "north_mid": ((603, -50), 180, "top_mid"),
            "north_right": ((969, -50), 180, "top_right"),
            # Left entry points (going right, angle=-90)
            "west_top": ((-50, 201), -90, "top_left"),
            "west_bottom": ((-50, 552), -90, "bottom_left"),
            # Right entry points (going left, angle=90)
            "east_top": ((1340, 135), 90, "top_right"),
            "east_bottom": ((1340, 486), 90, "bottom_right"),
        }
        
        # Define exit points (where cars leave the map)
        self.exit_points = {
            # Top exits (cars leaving northward)
            "north_left_exit": ((268, -50), 0, "top_left"),
            "north_mid_exit": ((627, -50), 0, "top_mid"),
            "north_right_exit": ((992, -50), 0, "top_right"),
            # Bottom exits (cars leaving southward)
            "south_left_exit": ((268, 780), 180, "bottom_left"),
            "south_mid_exit": ((627, 780), 180, "bottom_mid"),
            "south_right_exit": ((992, 780), 180, "bottom_right"),
            # Left exits (cars leaving westward)
            "west_top_exit": ((-50, 180), 90, "top_left"),
            "west_bottom_exit": ((-50, 530), 90, "bottom_left"),
            # Right exits (cars leaving eastward)
            "east_top_exit": ((1340, 180), -90, "top_right"),
            "east_bottom_exit": ((1340, 530), -90, "bottom_right"),
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
        
        Args:
            start_id: ID of the starting intersection
            goal_id: ID of the goal intersection
        
        Returns:
            List of intersection IDs representing the path, or None if no path exists
        """
        if start_id not in self.network.nodes or goal_id not in self.network.nodes:
            return None
        
        start = self.network.nodes[start_id]
        goal = self.network.nodes[goal_id]
        
        # Priority queue: (f_score, node_id)
        open_set = [(0, start_id)]
        heapq.heapify(open_set)
        
        # Track where we came from
        came_from: Dict[str, str] = {}
        
        # g_score: cost from start to node
        g_score: Dict[str, float] = {node_id: float('inf') for node_id in self.network.nodes}
        g_score[start_id] = 0
        
        # f_score: g_score + heuristic
        f_score: Dict[str, float] = {node_id: float('inf') for node_id in self.network.nodes}
        f_score[start_id] = self.network._heuristic(start, goal)
        
        # Track nodes in open set
        open_set_hash = {start_id}
        
        while open_set:
            _, current_id = heapq.heappop(open_set)
            open_set_hash.discard(current_id)
            
            if current_id == goal_id:
                return self._reconstruct_path(came_from, current_id)
            
            current = self.network.nodes[current_id]
            
            for neighbor_id, neighbor in current.neighbors.items():
                # Cost to move to neighbor (uniform cost of 1 per intersection)
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
        
        return None  # No path found
    
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
        if abs(dx) > abs(dy):
            # Primarily horizontal movement
            target_angle = -90 if dx > 0 else 90  # -90 = right, 90 = left
        else:
            # Primarily vertical movement
            target_angle = 0 if dy < 0 else 180  # 0 = up, 180 = down
        
        # Normalize angles to compare
        current_normalized = current_angle % 360
        target_normalized = target_angle % 360
        if current_normalized < 0:
            current_normalized += 360
        if target_normalized < 0:
            target_normalized += 360
        
        # Calculate the angle difference
        diff = (target_normalized - current_normalized + 360) % 360
        
        if diff == 0 or diff == 360:
            return "forward"
        elif diff == 90 or diff == -270:
            return "left"
        elif diff == 270 or diff == -90:
            return "right"
        elif diff == 180:
            # U-turn needed - default to left
            return "left"
        
        return "forward"


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
    
    Args:
        start_entry: Entry point ID (e.g., "south_left")
        destination_exit: Exit point ID (e.g., "north_right_exit")
    
    Returns:
        List of intersection IDs to pass through, or None if no route exists
    """
    network = get_traffic_network()
    pathfinder = get_pathfinder()
    
    # Get the nearest intersections to entry and exit
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
    """Get a random valid destination exit point for a given entry."""
    import random
    network = get_traffic_network()
    
    # Get all exit points that are different from the entry direction
    entry_pos = network.entry_points.get(entry_point, ((0, 0), 0, ""))
    
    # Filter exits that make sense (not going back the same way)
    valid_exits = list(network.exit_points.keys())
    
    return random.choice(valid_exits)


