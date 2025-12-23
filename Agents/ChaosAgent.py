import asyncio
from datetime import datetime, timedelta
import random

from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour, CyclicBehaviour
from spade.message import Message
from spade.template import Template

from Environment.environment import DisruptionType, INTERSECTION_IDS


class ChaosAgent(Agent):
    """
    Chaos Agent that manages perturbations in the environment.
    
    Responsibilities:
    - Automatically spawn and clear perturbations at intersections
    - Accidents are more common, other perturbations are rare
    - Ensures each intersection has at most 1 perturbation at any time
    - Coordinates with manual keyboard controls
    """
    
    def __init__(self, jid, password, environment):
        super().__init__(jid, password)
        self.environment = environment
        self.id = jid
        
        # Probability weights for different disruption types
        # Accidents are more common (weight 60), others are rare (weight 20 each)
        self.disruption_weights = {
            DisruptionType.ACCIDENT: 60,      # Most common
            DisruptionType.CONSTRUCTION: 20,   # Rare
            DisruptionType.ROAD_CLOSURE: 20,  # Rare
        }
        
        # Total weight for probability calculation
        self.total_weight = sum(self.disruption_weights.values())
        
        # Probability of spawning a new perturbation per check
        # Lower value = less frequent perturbations
        self.spawn_probability = 0.15  # 15% chance per check
        
        # Probability of clearing an existing perturbation per check
        # Higher value = shorter duration perturbations
        self.clear_probability = 0.20  # 20% chance per check
        
        # Probability of having multiple intersections with perturbations
        # Lower value = rare for more than 1 intersection to have perturbations
        self.multiple_intersections_probability = 0.10  # 10% chance
        
        # Track which intersections have perturbations managed by this agent
        # (to coordinate with manual controls)
        self.managed_intersections = set()
        
        # Minimum time between spawning perturbations at the same intersection (in simulation time)
        self.min_time_between_spawns = timedelta(seconds=30)  # 30 seconds minimum (simulation time)
        self.last_spawn_times = {}  # {intersection_id: simulation_time}

    async def setup(self):
        print(f"[CHAOS AGENT {self.jid}] Agente iniciado")
        # print(f"[CHAOS AGENT] Probabilidades: Acidente={self.disruption_weights[DisruptionType.ACCIDENT]/self.total_weight*100:.1f}%, "
        #       f"Obras={self.disruption_weights[DisruptionType.CONSTRUCTION]/self.total_weight*100:.1f}%, "
        #       f"Estrada Cortada={self.disruption_weights[DisruptionType.ROAD_CLOSURE]/self.total_weight*100:.1f}%")

        # Main behavior: periodically check and manage perturbations
        class PerturbationManagementBehaviour(PeriodicBehaviour):
            async def run(self):
                await self.agent.manage_perturbations()

            async def on_end(self):
                pass  # Don't stop the agent when this ends

        # Check every 10 seconds
        check_interval = 10
        start_at = datetime.now() + timedelta(seconds=check_interval)
        period = PerturbationManagementBehaviour(period=check_interval, start_at=start_at)
        self.add_behaviour(period)

        # Behavior to receive messages from environment about manual changes
        class ReceiveManualChangeBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)
                if msg:
                    performative = msg.get_metadata("performative")
                    if performative == "inform":
                        # Environment notifies about manual changes
                        intersection_id = msg.get_metadata("intersection_id", "")
                        action = msg.get_metadata("action", "")
                        
                        if action == "manual_trigger":
                            # Manual trigger - remove from managed set if it was managed
                            if intersection_id in self.agent.managed_intersections:
                                self.agent.managed_intersections.discard(intersection_id)
                                # print(f"[CHAOS AGENT] Intersecção {intersection_id} agora gerida manualmente")
                        elif action == "manual_clear":
                            # Manual clear - can be managed again
                            if intersection_id in self.agent.managed_intersections:
                                self.agent.managed_intersections.discard(intersection_id)
                                # print(f"[CHAOS AGENT] Intersecção {intersection_id} limpa manualmente, pode ser gerida novamente")

        template = Template()
        template.set_metadata("protocol", "chaos-coordination")
        self.add_behaviour(ReceiveManualChangeBehaviour(), template)

    async def manage_perturbations(self):
        """Main method to manage perturbations - spawn new ones and clear old ones."""
        # First, check if we should clear existing perturbations
        await self._clear_existing_perturbations()
        
        # Then, check if we should spawn new perturbations
        await self._spawn_new_perturbations()

    async def _clear_existing_perturbations(self):
        """Clear existing perturbations based on probability."""
        active_disruptions = self.environment.active_disruptions.copy()
        
        for intersection_id, disruption_type in active_disruptions.items():
            # Only clear disruptions that we spawned (managed by us)
            # If it's not in managed_intersections, it was manually triggered, so we don't clear it
            if intersection_id not in self.managed_intersections:
                continue
            
            # Check if we should clear this perturbation
            if random.random() < self.clear_probability:
                # Clear the perturbation (managed_by_chaos=True since we spawned it)
                cleared = self.environment.clear_disruption_at_intersection(intersection_id, managed_by_chaos=True)
                if cleared:
                    self.managed_intersections.discard(intersection_id)
                    disruption_pt = self.environment.get_disruption_label(disruption_type)
                    intersection_pt = self.environment.get_intersection_name(intersection_id)
                    # print(f"[CHAOS AGENT] Limpou {disruption_pt} em {intersection_pt}")

    async def _spawn_new_perturbations(self):
        """Spawn new perturbations based on probability."""
        # Count how many intersections currently have perturbations
        active_count = len(self.environment.active_disruptions)
        total_intersections = len(INTERSECTION_IDS)
        
        # Determine if we should spawn a new perturbation
        should_spawn = False
        
        if active_count == 0:
            # No perturbations - can spawn one
            should_spawn = random.random() < self.spawn_probability
        elif active_count == 1:
            # One perturbation exists - rare chance to spawn another
            should_spawn = random.random() < (self.spawn_probability * self.multiple_intersections_probability)
        else:
            # Multiple perturbations - very rare to spawn more
            should_spawn = random.random() < (self.spawn_probability * self.multiple_intersections_probability * 0.5)
        
        if not should_spawn:
            return
        
        # Find available intersections (those without perturbations)
        available_intersections = [
            intersection_id for intersection_id in INTERSECTION_IDS
            if intersection_id not in self.environment.active_disruptions
        ]
        
        if not available_intersections:
            # All intersections have perturbations
            return
        
        # Select a random available intersection
        selected_intersection = random.choice(available_intersections)
        
        # Check minimum time between spawns for this intersection (use simulation time)
        current_sim_time = self.environment.simulation_time
        if selected_intersection in self.last_spawn_times:
            time_since_last = current_sim_time - self.last_spawn_times[selected_intersection]
            if time_since_last < self.min_time_between_spawns:
                # Too soon to spawn again at this intersection
                return
        
        # Select disruption type based on weights (accidents more common)
        disruption_type = self._select_disruption_type()
        
        # Spawn the perturbation
        success = self.environment.trigger_disruption_at_intersection(
            intersection_id=selected_intersection,
            disruption_type=disruption_type,
            managed_by_chaos=True
        )
        
        if success:
            self.managed_intersections.add(selected_intersection)
            self.last_spawn_times[selected_intersection] = current_sim_time
            disruption_pt = self.environment.get_disruption_label(disruption_type)
            intersection_pt = self.environment.get_intersection_name(selected_intersection)
            # print(f"[CHAOS AGENT] Spawned {disruption_pt} em {intersection_pt}")

    def _select_disruption_type(self):
        """Select a disruption type based on probability weights."""
        rand = random.random() * self.total_weight
        cumulative = 0
        
        for disruption_type, weight in self.disruption_weights.items():
            cumulative += weight
            if rand <= cumulative:
                return disruption_type
        
        # Fallback to accident (most common)
        return DisruptionType.ACCIDENT

