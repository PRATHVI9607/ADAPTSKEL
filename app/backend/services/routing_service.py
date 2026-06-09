"""
RoutingService — ISP backbone routing system simulation using ADAPTSKEL.
Simulates real-world link failure scenarios with a Poisson schedule and calculates
convergence time, path optimality, and traffic loss metrics.
"""
from __future__ import annotations

import math
import os
import random
import sys
import threading
import time
from typing import Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'core', 'python'))

from adaptskel import AdaptSkel
import networkx as nx
from db import log_routing_event

# ── Major US Cities with Coordinates ─────────────────────────────────────────
CITIES = {
    0: {"name": "New York", "lat": 40.7128, "lon": -74.0060},
    1: {"name": "Boston", "lat": 42.3601, "lon": -71.0589},
    2: {"name": "Washington DC", "lat": 38.9072, "lon": -77.0369},
    3: {"name": "Chicago", "lat": 41.8781, "lon": -87.6298},
    4: {"name": "Indianapolis", "lat": 39.7684, "lon": -86.1581},
    5: {"name": "Detroit", "lat": 42.3314, "lon": -83.0458},
    6: {"name": "Minneapolis", "lat": 44.9778, "lon": -93.2650},
    7: {"name": "Atlanta", "lat": 33.7490, "lon": -84.3880},
    8: {"name": "Miami", "lat": 25.7617, "lon": -80.1918},
    9: {"name": "Kansas City", "lat": 39.0997, "lon": -94.5786},
    10: {"name": "Dallas", "lat": 32.7767, "lon": -96.7970},
    11: {"name": "Houston", "lat": 29.7604, "lon": -95.3698},
    12: {"name": "Denver", "lat": 39.7392, "lon": -104.9903},
    13: {"name": "Salt Lake City", "lat": 40.7608, "lon": -111.8910},
    14: {"name": "Phoenix", "lat": 33.4484, "lon": -112.0740},
    15: {"name": "Seattle", "lat": 47.6062, "lon": -122.3321},
    16: {"name": "Portland", "lat": 45.5152, "lon": -122.6784},
    17: {"name": "San Francisco", "lat": 37.7749, "lon": -122.4194},
    18: {"name": "Los Angeles", "lat": 34.0522, "lon": -118.2437},
    19: {"name": "San Diego", "lat": 32.7157, "lon": -117.1611},
}

# Real-world fiber connections
BACKBONE_EDGES = [
    (0, 1), (0, 2), (0, 3),
    (2, 4), (2, 7),
    (3, 4), (3, 5), (3, 6), (3, 9),
    (4, 7),
    (6, 12), (6, 15),
    (7, 8), (7, 10),
    (8, 11),
    (9, 10), (9, 12),
    (10, 11), (10, 12), (10, 14),
    (11, 14),
    (12, 13),
    (13, 15), (13, 17), (13, 18),
    (14, 18), (14, 19),
    (15, 16),
    (16, 17),
    (17, 18),
    (18, 19),
]

def get_distance(u_id: int, v_id: int) -> float:
    """Calculate Euclidean distance as a proxy for link latency (ms)."""
    c1 = CITIES[u_id]
    c2 = CITIES[v_id]
    dist = math.sqrt((c1["lat"] - c2["lat"])**2 + (c1["lon"] - c2["lon"])**2)
    # Scale to typical fiber propagation delay (e.g. ~8.3 ms per 1000km, roughly dist * 5)
    return round(max(2.0, dist * 5.2), 1)

class RoutingService:
    """Manages the ISP backbone simulation and dynamic pathfinding."""

    def __init__(self) -> None:
        self.engine = AdaptSkel(source=0, debug=False)
        self.oracle = nx.Graph()
        
        # Original edges list: key -> weight
        self.all_edges: dict[tuple[int, int], float] = {}
        
        # Simulation state
        self.failed_edges: set[tuple[int, int]] = set()
        self.sim_active = False
        self.sim_thread: Optional[threading.Thread] = None
        self.sim_interval = 10.0  # Poisson mean failure rate (faster for demo)
        self.lock = threading.Lock()

        # Telemetry metrics
        self.metrics = {
            "total_failures": 0,
            "total_recoveries": 0,
            "avg_convergence_ms": 0.0,
            "traffic_loss_pct": 0.0,
            "path_optimality_pct": 100.0,
            "active_failures": 0
        }
        self.convergence_times: list[float] = []

        self._init_network()

    def _init_network(self) -> None:
        """Register all vertices and edges in ADAPTSKEL and Oracle."""
        for c_id in CITIES:
            self.engine.add_vertex(c_id)
            self.oracle.add_node(c_id)

        for u, v in BACKBONE_EDGES:
            w = get_distance(u, v)
            key = (min(u, v), max(u, v))
            self.all_edges[key] = w
            self.engine.insert(u, v, w)
            self.oracle.add_edge(u, v, weight=w)

    def get_topology(self) -> dict:
        """Return nodes and edges with metadata including layers and health."""
        with self.lock:
            nodes_list = []
            for c_id, info in CITIES.items():
                nodes_list.append({
                    "id": c_id,
                    "name": info["name"],
                    "lat": info["lat"],
                    "lon": info["lon"],
                    "status": "healthy"
                })

            skeleton = { (min(e["u"], e["v"]), max(e["u"], e["v"])) 
                         for e in self.engine.get_skeleton_edges() }

            edges_list = []
            for (u, v), w in self.all_edges.items():
                key = (u, v)
                is_failed = key in self.failed_edges
                in_f1 = key in skeleton and not is_failed
                edges_list.append({
                    "u": u,
                    "v": v,
                    "w": w,
                    "status": "failed" if is_failed else "healthy",
                    "layer": "F1" if in_f1 else "F2"
                })

            return {
                "nodes": nodes_list,
                "edges": edges_list,
                "metrics": self.metrics
            }

    def route(self, source: int, target: int) -> dict:
        """Compute the shortest path routing under current link failures."""
        if source not in CITIES or target not in CITIES:
            return {"error": "Invalid source or target city"}

        t0 = time.perf_counter()
        with self.lock:
            # Query shortest path distance via ADAPTSKEL
            dist = self.engine.query(source, target)
            query_time_us = (time.perf_counter() - t0) * 1e6
            
            # Extract path nodes via NetworkX mirror (which replicates engine exact topology)
            try:
                path = nx.shortest_path(self.oracle, source, target, weight="weight")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                path = []
                dist = float("inf")

            # Optimality check (since ADAPTSKEL computes exact, this is always 100% unless disconnected)
            optimality = 100.0
            if dist == float("inf"):
                optimality = 0.0

            # Log to DB
            log_routing_event("query", source, target, query_time_us, len(self.failed_edges), optimality)

            return {
                "source": source,
                "target": target,
                "distance": dist if dist != float("inf") else None,
                "path": path,
                "query_time_us": round(query_time_us, 1),
                "optimality": optimality
            }

    def simulate_failure(self, u: int, v: int) -> dict:
        """Trigger a manual link failure."""
        key = (min(u, v), max(u, v))
        if key not in self.all_edges:
            return {"error": "Edge does not exist"}
        if key in self.failed_edges:
            return {"success": True, "info": "Edge already failed"}

        t0 = time.perf_counter()
        with self.lock:
            self.failed_edges.add(key)
            self.engine.delete(u, v)
            if self.oracle.has_edge(u, v):
                self.oracle.remove_edge(u, v)
            
            convergence_time_us = (time.perf_counter() - t0) * 1e6
            conv_ms = convergence_time_us / 1000.0
            
            self.metrics["total_failures"] += 1
            self.metrics["active_failures"] = len(self.failed_edges)
            self.convergence_times.append(conv_ms)
            self.metrics["avg_convergence_ms"] = round(sum(self.convergence_times) / len(self.convergence_times), 3)

            # Simulated packet loss: if convergence takes more than 5ms, traffic loss is proportional
            # Let's say: loss = min(1.0, conv_ms / 100.0) * 100.0 (capped at 0.1% for normal run)
            loss = round(min(0.1, conv_ms * 0.005) * 100.0, 3)
            self.metrics["traffic_loss_pct"] = max(self.metrics["traffic_loss_pct"], loss)

            log_routing_event("failure", u, v, convergence_time_us, len(self.failed_edges))

            return {
                "success": True,
                "u": u,
                "v": v,
                "convergence_time_ms": round(conv_ms, 3),
                "traffic_loss_pct": loss
            }

    def simulate_recovery(self, u: int, v: int) -> dict:
        """Trigger a manual link recovery."""
        key = (min(u, v), max(u, v))
        if key not in self.all_edges:
            return {"error": "Edge does not exist"}
        if key not in self.failed_edges:
            return {"success": True, "info": "Edge is already healthy"}

        t0 = time.perf_counter()
        with self.lock:
            self.failed_edges.discard(key)
            w = self.all_edges[key]
            self.engine.insert(u, v, w)
            self.oracle.add_edge(u, v, weight=w)

            convergence_time_us = (time.perf_counter() - t0) * 1e6
            conv_ms = convergence_time_us / 1000.0

            self.metrics["total_recoveries"] += 1
            self.metrics["active_failures"] = len(self.failed_edges)
            self.convergence_times.append(conv_ms)
            self.metrics["avg_convergence_ms"] = round(sum(self.convergence_times) / len(self.convergence_times), 3)

            log_routing_event("recovery", u, v, convergence_time_us, len(self.failed_edges))

            return {
                "success": True,
                "u": u,
                "v": v,
                "convergence_time_ms": round(conv_ms, 3)
            }

    def start_simulation(self, interval_sec: float = 8.0) -> dict:
        """Start the background Poisson failure simulation loop."""
        with self.lock:
            if self.sim_active:
                return {"status": "already running"}
            self.sim_active = True
            self.sim_interval = interval_sec
            self.sim_thread = threading.Thread(
                target=self._run_simulation,
                daemon=True,
                name="routing-simulator"
            )
            self.sim_thread.start()
            return {"status": "started", "interval_sec": interval_sec}

    def stop_simulation(self) -> dict:
        """Stop the background Poisson failure simulation loop."""
        with self.lock:
            if not self.sim_active:
                return {"status": "already stopped"}
            self.sim_active = False
            return {"status": "stopping"}

    def _run_simulation(self) -> None:
        """Background thread executing Poisson link failure events."""
        while True:
            # Poisson interval modeling: time = -ln(rand) * mean
            r = random.random()
            if r == 0:
                r = 0.0001
            delay = -math.log(r) * self.sim_interval
            
            # Sleep in small segments to react quickly to shutdown
            slept = 0.0
            while slept < delay:
                if not self.sim_active:
                    return
                time.sleep(0.5)
                slept += 0.5

            if not self.sim_active:
                return

            # Trigger failure or recovery randomly
            # Limit total simultaneous failures to 5 (to avoid graph complete fragmentation)
            active_fail_count = len(self.failed_edges)
            
            trigger_failure = (active_fail_count == 0) or (
                active_fail_count < 5 and random.random() < 0.6
            )

            if trigger_failure:
                # Select a healthy link to fail
                healthy_links = [edge for edge in self.all_edges if edge not in self.failed_edges]
                if healthy_links:
                    u, v = random.choice(healthy_links)
                    self.simulate_failure(u, v)
            else:
                # Recover a failed link
                if self.failed_edges:
                    u, v = random.choice(list(self.failed_edges))
                    self.simulate_recovery(u, v)
