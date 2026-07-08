"""
RoutingService — ISP backbone routing system simulation using ADAPTSKEL.
Simulates real-world link failure scenarios with a Poisson schedule and calculates
convergence time, path optimality, and traffic loss metrics.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any, Optional

# Add core/python to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'core', 'python'))

from routing.simulation import ISPRoutingSimulation
from db import log_routing_event

class RoutingService:
    """Manages the ISP backbone simulation and dynamic pathfinding."""

    def __init__(self) -> None:
        self.sim = ISPRoutingSimulation(db_log_callback=log_routing_event)
        
        # Simulation speed factor (e.g. 50,000x to accelerate Poisson events)
        self.sim_speed = 50000.0
        self.sim_active = False
        self.sim_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # Telemetry metrics
        self.metrics = {
            "total_failures": 0,
            "total_recoveries": 0,
            "avg_convergence_ms": 0.0,
            "traffic_loss_pct": 0.0,
            "path_optimality_pct": 100.0,
            "active_failures": 0,
            # Congestion-aware routing telemetry
            "baseline_loss_pct": 0.0,
            "congestion_aware_loss_pct": 0.0,
            "congestion_improvement_pct": 0.0,
        }

    def get_topology(self) -> dict:
        """Return nodes and edges with metadata including layers and health."""
        with self.lock:
            nodes_list = []
            for city in self.sim.topology.cities:
                # Find if this node is disconnected
                nodes_list.append({
                    "id": city.id,
                    "name": city.name,
                    "lat": city.lat,
                    "lon": city.lon,
                    "population": city.population,
                    "status": "healthy"
                })

            skeleton = { (min(e["u"], e["v"]), max(e["u"], e["v"])) 
                         for e in self.sim.adaptskel.get_skeleton_edges() }

            edges_list = []
            for link in self.sim.topology.links:
                key = (min(link.u, link.v), max(link.u, link.v))
                is_failed = key in self.sim.failure_sim.failed_links
                in_f1 = key in skeleton and not is_failed
                edges_list.append({
                    "u": link.u,
                    "v": link.v,
                    "w": link.latency_ms,
                    "capacity": link.capacity_gbps,
                    "status": "failed" if is_failed else "healthy",
                    "layer": "F1" if in_f1 else "F2"
                })

            # Retrieve report metrics
            rep = self.sim.metrics.report()
            live_slos = self.sim.evaluate_current_slos()
            self.metrics.update({
                "avg_convergence_ms": rep["avg_convergence_ms"],
                "traffic_loss_pct": live_slos["traffic_loss_pct"],
                "path_optimality_pct": live_slos["path_optimality_pct"],
                "active_failures": len(self.sim.failure_sim.failed_links),
                "baseline_loss_pct": live_slos["baseline_loss_pct"],
                "congestion_aware_loss_pct": live_slos["congestion_aware_loss_pct"],
                "congestion_improvement_pct": live_slos["congestion_improvement_pct"],
            })

            return {
                "nodes": nodes_list,
                "edges": edges_list,
                "metrics": self.metrics
            }

    def route(self, source: int, target: int) -> dict:
        """Compute the shortest path routing under current link failures."""
        with self.lock:
            res = self.sim.route_engine.route(source, target)
            if not res["path"] and source != target:
                return {"error": f"No path found between router {source} and {target}"}
                
            return {
                "source": res["source"],
                "target": res["destination"],
                "distance": res["latency_ms"] if res["latency_ms"] != float('inf') else None,
                "path": res["path"],
                "query_time_us": round(res["convergence_ms"] * 1000.0, 1),
                "optimality": 100.0 if res["latency_ms"] != float('inf') else 0.0,
                "bottleneck_gbps": res["bottleneck_gbps"]
            }

    def simulate_failure(self, u: int, v: int) -> dict:
        """Trigger a manual link failure."""
        with self.lock:
            res = self.sim.trigger_manual_failure(u, v)
            if "error" in res:
                return res
            self.metrics["total_failures"] += 1
            live_slos = self.sim.evaluate_current_slos()
            self.metrics.update({
                "traffic_loss_pct": live_slos["traffic_loss_pct"],
                "path_optimality_pct": live_slos["path_optimality_pct"],
                "active_failures": len(self.sim.failure_sim.failed_links),
            })
            return {
                "success": True,
                "u": u,
                "v": v,
                "convergence_time_ms": res["convergence_time_ms"],
                "traffic_loss_pct": live_slos["traffic_loss_pct"],
                "path_optimality_pct": live_slos["path_optimality_pct"]
            }

    def simulate_recovery(self, u: int, v: int) -> dict:
        """Trigger a manual link recovery."""
        with self.lock:
            res = self.sim.trigger_manual_recovery(u, v)
            if "error" in res:
                return res
            self.metrics["total_recoveries"] += 1
            live_slos = self.sim.evaluate_current_slos()
            self.metrics.update({
                "traffic_loss_pct": live_slos["traffic_loss_pct"],
                "path_optimality_pct": live_slos["path_optimality_pct"],
                "active_failures": len(self.sim.failure_sim.failed_links),
            })
            return {
                "success": True,
                "u": u,
                "v": v,
                "convergence_time_ms": res["convergence_time_ms"],
                "traffic_loss_pct": live_slos["traffic_loss_pct"],
                "path_optimality_pct": live_slos["path_optimality_pct"]
            }

    def start_simulation(self, interval_sec: float = 8.0) -> dict:
        """
        Start the background Poisson failure simulation loop.
        interval_sec is translated into an appropriate speed factor.
        """
        with self.lock:
            self.sim_speed = 400000.0 / max(0.1, interval_sec)
            if self.sim_active:
                return {"status": "updated", "speed_factor": self.sim_speed}
            self.sim_active = True
            
            self.sim_thread = threading.Thread(
                target=self._run_simulation,
                daemon=True,
                name="routing-simulator-v2"
            )
            self.sim_thread.start()
            return {"status": "started", "speed_factor": self.sim_speed}

    def stop_simulation(self) -> dict:
        """Stop the background Poisson failure simulation loop."""
        with self.lock:
            if not self.sim_active:
                return {"status": "already stopped"}
            self.sim_active = False
            return {"status": "stopping"}

    def reset_simulation(self) -> dict:
        """Reset the simulation engine to initial healthy state."""
        was_active = self.sim_active
        if was_active:
            self.stop_simulation()
            
        with self.lock:
            self.sim = ISPRoutingSimulation(db_log_callback=log_routing_event)
            self.metrics = {
                "total_failures": 0,
                "total_recoveries": 0,
                "avg_convergence_ms": 0.0,
                "traffic_loss_pct": 0.0,
                "path_optimality_pct": 100.0,
                "active_failures": 0
            }
            
        if was_active:
            self.start_simulation()
            
        return {"status": "reset"}

    def get_csv_export(self) -> str:
        """Generate a CSV report of the simulation metrics."""
        rep = self.sim.metrics.report()
        lines = [
            "Metric,Value,Status",
            f"Avg Convergence (ms),{rep['avg_convergence_ms']},{'MET' if rep['convergence_slo_met'] else 'VIOLATED'}",
            f"P95 Convergence (ms),{rep['p95_convergence_ms']},-",
            f"P99 Convergence (ms),{rep['p99_convergence_ms']},-",
            f"Avg Traffic Loss (%),{rep['avg_traffic_loss_pct']},{'MET' if rep['traffic_loss_slo_met'] else 'VIOLATED'}",
            f"Max Traffic Loss (%),{rep['max_traffic_loss_pct']},-",
            f"Avg Path Optimality (%),{rep['avg_path_optimality_pct']},{'MET' if rep['optimality_slo_met'] else 'VIOLATED'}",
            f"Query Availability (%),{rep['availability_pct']},{'MET' if rep['availability_slo_met'] else 'VIOLATED'}",
            f"Active Failures,{len(self.sim.failure_sim.failed_links)},-"
        ]
        return "\n".join(lines)

    def _run_simulation(self) -> None:
        """Background thread executing Poisson link failure events using step()."""
        while True:
            with self.lock:
                if not self.sim_active:
                    return
                # Get next event delay in simulated seconds
                delay, event_type, link = self.sim.failure_sim.get_next_event_delay(
                    self.sim.current_sim_time, self.sim.active_failures_limit
                )

            # Sleep duration in real wall-clock seconds is delay / sim_speed
            # Limit minimum sleep to avoid high-CPU spins if delay is very small
            real_sleep = max(0.1, min(10.0, delay / self.sim_speed))

            # Sleep in small segments to react quickly to shutdown
            slept = 0.0
            while slept < real_sleep:
                if not self.sim_active:
                    return
                time.sleep(min(0.2, real_sleep - slept))
                slept += 0.2

            with self.lock:
                if not self.sim_active:
                    return
                # Advance simulation and execute step
                step_res = self.sim.step()
                
                # Increment metrics counters
                if step_res["event"] == "failure":
                    self.metrics["total_failures"] += 1
                elif step_res["event"] == "recovery":
                    self.metrics["total_recoveries"] += 1
