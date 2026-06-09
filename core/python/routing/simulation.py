import time
import random
from typing import List, Dict, Any, Tuple, Optional, Callable
import networkx as nx
from adaptskel import AdaptSkel
from routing.topology import BackboneTopology, Link, haversine_distance
from routing.failures import LinkFailureSimulator
from routing.traffic import TrafficDemandSimulator
from routing.routing import RouteComputationEngine
from routing.metrics import MetricsTracker

class ISPRoutingSimulation:
    """Orchestrates the entire ISP backbone routing simulation including traffic, failures, and metrics."""
    def __init__(
        self,
        num_cities: int = 50,
        mtbf_hours: float = 100000.0,
        mean_recovery_min: float = 5.0,
        num_demands: int = 100,
        db_log_callback: Optional[Callable[[str, int, int, float, int, float], None]] = None
    ) -> None:
        self.topology = BackboneTopology()
        self.adaptskel = AdaptSkel(source=0, debug=False)
        
        # Link keys: sorted (min, max) representation
        self.link_keys = [(min(l.u, l.v), max(l.u, l.v)) for l in self.topology.links]
        
        self.failure_sim = LinkFailureSimulator(
            links_keys=self.link_keys,
            mtbf_hours=mtbf_hours,
            mean_recovery_min=mean_recovery_min
        )
        
        self.traffic_sim = TrafficDemandSimulator(
            cities=self.topology.cities,
            num_demands=num_demands
        )
        
        self.route_engine = RouteComputationEngine(
            adaptskel=self.adaptskel,
            topology=self.topology
        )
        
        self.metrics = MetricsTracker()
        self.db_log_callback = db_log_callback
        
        self.current_sim_time = 0.0  # in seconds
        self.active_failures_limit = 5
        
        self._init_engine()

    def _init_engine(self) -> None:
        """Register all vertices and edges in ADAPTSKEL."""
        for city in self.topology.cities:
            self.adaptskel.add_vertex(city.id)
            
        for link in self.topology.links:
            self.adaptskel.insert(link.u, link.v, link.latency_ms)

    def trigger_manual_failure(self, u: int, v: int) -> Dict[str, Any]:
        """Manually trigger a link failure on the network."""
        key = (min(u, v), max(u, v))
        if key not in self.link_keys:
            return {"error": "Link does not exist"}
        if key in self.failure_sim.failed_links:
            return {"error": "Link already failed"}

        t0 = time.perf_counter()
        # Delete from ADAPTSKEL
        self.adaptskel.delete(u, v)
        # Record failure in simulator
        recovery_dur = self.failure_sim.record_failure(key, self.current_sim_time)
        self.route_engine.update_link_status(u, v, is_failed=True)
        
        conv_time_ms = (time.perf_counter() - t0) * 1000.0
        self.metrics.measure_convergence_time(conv_time_ms)
        
        # Track accuracy with oracle
        self._verify_against_oracle(u, v)

        # Log event to database if callback is provided
        if self.db_log_callback:
            self.db_log_callback("failure", u, v, conv_time_ms * 1000.0, len(self.failure_sim.failed_links), 100.0)

        return {
            "u": u,
            "v": v,
            "event": "failure",
            "convergence_time_ms": round(conv_time_ms, 3),
            "recovery_duration_sec": round(recovery_dur, 1)
        }

    def trigger_manual_recovery(self, u: int, v: int) -> Dict[str, Any]:
        """Manually trigger link recovery."""
        key = (min(u, v), max(u, v))
        if key not in self.link_keys:
            return {"error": "Link does not exist"}
        if key not in self.failure_sim.failed_links:
            return {"error": "Link is healthy"}

        t0 = time.perf_counter()
        # Re-insert into ADAPTSKEL
        link = next(l for l in self.topology.links if (min(l.u, l.v), max(l.u, l.v)) == key)
        self.adaptskel.insert(u, v, link.latency_ms)
        
        # Recover in simulator
        self.failure_sim.record_recovery(key)
        self.route_engine.update_link_status(u, v, is_failed=False)
        
        conv_time_ms = (time.perf_counter() - t0) * 1000.0
        self.metrics.measure_convergence_time(conv_time_ms)
        
        # Track accuracy with oracle
        self._verify_against_oracle(u, v)

        # Log event to database if callback is provided
        if self.db_log_callback:
            self.db_log_callback("recovery", u, v, conv_time_ms * 1000.0, len(self.failure_sim.failed_links), 100.0)

        return {
            "u": u,
            "v": v,
            "event": "recovery",
            "convergence_time_ms": round(conv_time_ms, 3)
        }

    def step(self) -> Dict[str, Any]:
        """
        Execute one simulation step by finding the next failure/recovery event,
        updating topology, running traffic simulation, and measuring metrics.
        """
        delay, event_type, link = self.failure_sim.get_next_event_delay(
            self.current_sim_time, self.active_failures_limit
        )
        
        # Advance simulation time
        self.current_sim_time += delay
        u, v = link
        
        event_details = {}
        if event_type == "failure":
            event_details = self.trigger_manual_failure(u, v)
        elif event_type == "recovery":
            event_details = self.trigger_manual_recovery(u, v)
            
        # Simulate traffic demands for current hour
        hour = int((self.current_sim_time // 3600) % 24)
        demands = self.traffic_sim.generate_demands(hour)
        
        # Route demands and compute metrics
        routed_results = []
        optimal_latencies = []
        
        for d in demands:
            res = self.route_engine.route(d["source"], d["destination"])
            routed_results.append(res)
            
            # Query oracle shortest path for comparison
            # nx.shortest_path_length on self.adaptskel._G gives the exact shortest path length
            try:
                opt_dist = nx.shortest_path_length(self.adaptskel._G, d["source"], d["destination"], weight="weight")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                opt_dist = float('inf')
            optimal_latencies.append(opt_dist)
            
            # Record query accuracy for Availability
            is_correct = (res["latency_ms"] == float('inf') and opt_dist == float('inf')) or (
                res["latency_ms"] != float('inf') and opt_dist != float('inf') and abs(res["latency_ms"] - opt_dist) < 1e-4
            )
            self.metrics.track_query_accuracy(is_correct)
            
        # Record traffic loss and path optimality
        loss_pct = self.metrics.measure_traffic_loss(demands, routed_results)
        optimality_pct = self.metrics.measure_path_optimality(routed_results, optimal_latencies)
        
        return {
            "sim_time": self.current_sim_time,
            "event": event_type,
            "link": link,
            "convergence_time_ms": event_details.get("convergence_time_ms", 0.0),
            "traffic_loss_pct": loss_pct,
            "path_optimality_pct": optimality_pct,
            "active_failures": len(self.failure_sim.failed_links)
        }

    def _verify_against_oracle(self, u: int, v: int) -> None:
        """Verify routing accuracy for a test query when topology changes."""
        # Simple test query from node 0 to 49
        try:
            adaptskel_dist = self.adaptskel.query(0, 49)
            oracle_dist = nx.shortest_path_length(self.adaptskel._G, 0, 49, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            adaptskel_dist = float('inf')
            oracle_dist = float('inf')
            
        is_correct = (adaptskel_dist == float('inf') and oracle_dist == float('inf')) or (
            adaptskel_dist != float('inf') and oracle_dist != float('inf') and abs(adaptskel_dist - oracle_dist) < 1e-4
        )
        self.metrics.track_query_accuracy(is_correct)

    def run_simulation_loop(self, duration_hours: float = 1.0) -> List[Dict[str, Any]]:
        """Run a batch simulation for the specified duration and return a log of events."""
        duration_seconds = duration_hours * 3600.0
        log = []
        while self.current_sim_time < duration_seconds:
            step_res = self.step()
            log.append(step_res)
        return log
