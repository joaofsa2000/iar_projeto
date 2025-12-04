# Data/MetricsManager.py
"""
Metrics Manager for saving simulation data for analysis and ML model training.
Saves data in CSV format for easy processing with pandas, sklearn, etc.
"""

import csv
import os
from datetime import datetime
from typing import Dict, List, Any


class MetricsManager:
    """Manages saving and loading of simulation metrics."""
    
    def __init__(self, data_dir: str = "Data"):
        self.data_dir = data_dir
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # File paths
        self.traffic_flow_file = os.path.join(data_dir, f"traffic_flow_{self.session_id}.csv")
        self.waiting_times_file = os.path.join(data_dir, f"waiting_times_{self.session_id}.csv")
        self.congestion_file = os.path.join(data_dir, f"congestion_{self.session_id}.csv")
        self.disruptions_file = os.path.join(data_dir, f"disruptions_{self.session_id}.csv")
        self.system_snapshots_file = os.path.join(data_dir, f"system_snapshots_{self.session_id}.csv")
        self.intersection_metrics_file = os.path.join(data_dir, f"intersection_metrics_{self.session_id}.csv")
        
        # Initialize files with headers
        self._init_files()
        
        # In-memory buffers for batch writing
        self.traffic_flow_buffer = []
        self.waiting_times_buffer = []
        self.congestion_buffer = []
        self.disruptions_buffer = []
        self.system_snapshots_buffer = []
        self.intersection_metrics_buffer = []
        
        # Buffer size before flushing to disk
        self.buffer_size = 50
        
        print(f"[METRICS] Sessão iniciada: {self.session_id}")
        print(f"[METRICS] Dados serão guardados em: {data_dir}/")
    
    def _init_files(self):
        """Initialize CSV files with headers."""
        
        # Traffic Flow: vehicles entering/exiting intersections
        with open(self.traffic_flow_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'sim_time', 'sim_hour', 'intersection_id',
                'vehicles_passed', 'direction', 'vehicle_type'
            ])
        
        # Waiting Times: time vehicles wait at traffic lights
        with open(self.waiting_times_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'sim_time', 'sim_hour', 'car_id', 'traffic_light_id',
                'waiting_time_seconds', 'intersection_id'
            ])
        
        # Congestion: congestion levels per intersection over time
        with open(self.congestion_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'sim_time', 'sim_hour', 'intersection_id',
                'congestion_level', 'stopped_vehicles', 'traffic_density'
            ])
        
        # Disruptions: disruption events and their effects
        with open(self.disruptions_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'sim_time', 'sim_hour', 'disruption_type',
                'intersection_id', 'is_global', 'duration_seconds', 'speed_modifier'
            ])
        
        # System Snapshots: periodic snapshots of entire system state
        with open(self.system_snapshots_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'sim_time', 'sim_hour', 'sim_day_of_week',
                'total_cars', 'total_emergency_cars', 'total_stopped',
                'avg_speed', 'avg_waiting_time', 'traffic_density',
                'active_disruptions', 'global_disruption', 'speed_modifier',
                'time_speed_multiplier', 'is_paused'
            ])
        
        # Intersection Metrics: detailed per-intersection data
        with open(self.intersection_metrics_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'sim_time', 'sim_hour', 'intersection_id',
                'vehicles_passed_total', 'congestion_level', 'has_disruption',
                'disruption_type', 'vertical_light_state', 'horizontal_light_state'
            ])
    
    def record_traffic_flow(self, sim_time: datetime, intersection_id: str,
                           vehicles_passed: int, direction: str = "unknown",
                           vehicle_type: str = "car"):
        """Record vehicle flow through an intersection."""
        self.traffic_flow_buffer.append([
            datetime.now().isoformat(),
            sim_time.isoformat(),
            sim_time.hour,
            intersection_id,
            vehicles_passed,
            direction,
            vehicle_type
        ])
        
        if len(self.traffic_flow_buffer) >= self.buffer_size:
            self._flush_traffic_flow()
    
    def record_waiting_time(self, sim_time: datetime, car_id: str,
                           traffic_light_id: str, waiting_time_seconds: float,
                           intersection_id: str):
        """Record a vehicle's waiting time at a traffic light."""
        self.waiting_times_buffer.append([
            datetime.now().isoformat(),
            sim_time.isoformat(),
            sim_time.hour,
            car_id,
            traffic_light_id,
            round(waiting_time_seconds, 2),
            intersection_id
        ])
        
        if len(self.waiting_times_buffer) >= self.buffer_size:
            self._flush_waiting_times()
    
    def record_congestion(self, sim_time: datetime, intersection_id: str,
                         congestion_level: float, stopped_vehicles: int,
                         traffic_density: float):
        """Record congestion level at an intersection."""
        self.congestion_buffer.append([
            datetime.now().isoformat(),
            sim_time.isoformat(),
            sim_time.hour,
            intersection_id,
            round(congestion_level, 3),
            stopped_vehicles,
            round(traffic_density, 3)
        ])
        
        if len(self.congestion_buffer) >= self.buffer_size:
            self._flush_congestion()
    
    def record_disruption(self, sim_time: datetime, disruption_type: str,
                         intersection_id: str, is_global: bool,
                         duration_seconds: float, speed_modifier: float):
        """Record a disruption event."""
        self.disruptions_buffer.append([
            datetime.now().isoformat(),
            sim_time.isoformat(),
            sim_time.hour,
            disruption_type,
            intersection_id if not is_global else "global",
            is_global,
            round(duration_seconds, 2),
            round(speed_modifier, 3)
        ])
        
        if len(self.disruptions_buffer) >= self.buffer_size:
            self._flush_disruptions()
    
    def record_system_snapshot(self, sim_time: datetime, total_cars: int,
                              total_emergency_cars: int, total_stopped: int,
                              avg_speed: float, avg_waiting_time: float,
                              traffic_density: float, active_disruptions: int,
                              global_disruption: str, speed_modifier: float,
                              time_speed_multiplier: int, is_paused: bool):
        """Record a snapshot of the entire system state."""
        self.system_snapshots_buffer.append([
            datetime.now().isoformat(),
            sim_time.isoformat(),
            sim_time.hour,
            sim_time.strftime("%A"),  # Day of week
            total_cars,
            total_emergency_cars,
            total_stopped,
            round(avg_speed, 2),
            round(avg_waiting_time, 2),
            round(traffic_density, 3),
            active_disruptions,
            global_disruption,
            round(speed_modifier, 3),
            time_speed_multiplier,
            is_paused
        ])
        
        if len(self.system_snapshots_buffer) >= self.buffer_size:
            self._flush_system_snapshots()
    
    def record_intersection_metrics(self, sim_time: datetime, intersection_id: str,
                                   vehicles_passed_total: int, congestion_level: float,
                                   has_disruption: bool, disruption_type: str,
                                   vertical_light_state: str, horizontal_light_state: str):
        """Record detailed metrics for a specific intersection."""
        self.intersection_metrics_buffer.append([
            datetime.now().isoformat(),
            sim_time.isoformat(),
            sim_time.hour,
            intersection_id,
            vehicles_passed_total,
            round(congestion_level, 3),
            has_disruption,
            disruption_type,
            vertical_light_state,
            horizontal_light_state
        ])
        
        if len(self.intersection_metrics_buffer) >= self.buffer_size:
            self._flush_intersection_metrics()
    
    def _flush_traffic_flow(self):
        """Write traffic flow buffer to disk."""
        if self.traffic_flow_buffer:
            with open(self.traffic_flow_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(self.traffic_flow_buffer)
            self.traffic_flow_buffer.clear()
    
    def _flush_waiting_times(self):
        """Write waiting times buffer to disk."""
        if self.waiting_times_buffer:
            with open(self.waiting_times_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(self.waiting_times_buffer)
            self.waiting_times_buffer.clear()
    
    def _flush_congestion(self):
        """Write congestion buffer to disk."""
        if self.congestion_buffer:
            with open(self.congestion_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(self.congestion_buffer)
            self.congestion_buffer.clear()
    
    def _flush_disruptions(self):
        """Write disruptions buffer to disk."""
        if self.disruptions_buffer:
            with open(self.disruptions_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(self.disruptions_buffer)
            self.disruptions_buffer.clear()
    
    def _flush_system_snapshots(self):
        """Write system snapshots buffer to disk."""
        if self.system_snapshots_buffer:
            with open(self.system_snapshots_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(self.system_snapshots_buffer)
            self.system_snapshots_buffer.clear()
    
    def _flush_intersection_metrics(self):
        """Write intersection metrics buffer to disk."""
        if self.intersection_metrics_buffer:
            with open(self.intersection_metrics_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(self.intersection_metrics_buffer)
            self.intersection_metrics_buffer.clear()
    
    def flush_all(self):
        """Flush all buffers to disk."""
        self._flush_traffic_flow()
        self._flush_waiting_times()
        self._flush_congestion()
        self._flush_disruptions()
        self._flush_system_snapshots()
        self._flush_intersection_metrics()
        print(f"[METRICS] Todos os dados foram guardados")
    
    def save_session_summary(self, metrics_summary: Dict[str, Any]):
        """Save a summary of the entire session."""
        summary_file = os.path.join(self.data_dir, f"session_summary_{self.session_id}.csv")
        
        with open(summary_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['metric', 'value'])
            
            writer.writerow(['session_id', self.session_id])
            writer.writerow(['end_time', datetime.now().isoformat()])
            
            for key, value in metrics_summary.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        writer.writerow([f"{key}_{sub_key}", sub_value])
                else:
                    writer.writerow([key, value])
        
        print(f"[METRICS] Resumo da sessão guardado: {summary_file}")
    
    def get_session_files(self) -> Dict[str, str]:
        """Get paths to all session data files."""
        return {
            'traffic_flow': self.traffic_flow_file,
            'waiting_times': self.waiting_times_file,
            'congestion': self.congestion_file,
            'disruptions': self.disruptions_file,
            'system_snapshots': self.system_snapshots_file,
            'intersection_metrics': self.intersection_metrics_file,
        }


# Singleton instance
_metrics_manager = None


def get_metrics_manager() -> MetricsManager:
    """Get the singleton metrics manager instance."""
    global _metrics_manager
    if _metrics_manager is None:
        _metrics_manager = MetricsManager()
    return _metrics_manager

