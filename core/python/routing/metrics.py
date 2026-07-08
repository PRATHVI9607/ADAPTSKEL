from typing import List, Dict, Any
import numpy as np

class MetricsTracker:
    """Tracks and evaluates routing SLOs: convergence time, traffic loss, and path optimality."""
    def __init__(self) -> None:
        self.convergence_times: List[float] = []
        self.traffic_loss_events: List[float] = []
        self.path_optimality_scores: List[float] = []
        
        # Throughput & Availability tracking
        self.total_queries = 0
        self.correct_queries = 0
        self.query_start_time = 0.0

    def measure_convergence_time(self, conv_time_ms: float) -> float:
        """Record a convergence time (ms) for a failure/recovery event. SLO: <= 10ms."""
        self.convergence_times.append(conv_time_ms)
        return conv_time_ms

    @staticmethod
    def _lost_volume_gbps(demand: Dict[str, Any], result: Dict[str, Any]) -> float:
        """
        Volume of a single demand (Gbps) that fails to reach its destination.

        Two failure modes are modeled:
          1. Full outage — no path exists (or infinite latency): the entire
             demand is dropped.
          2. Congestion — a path exists but its bottleneck link capacity
             (`bottleneck_gbps`, the minimum link capacity along the route)
             is lower than the demand's volume: only `bottleneck_gbps` worth
             of the demand gets through and the excess is dropped.

        Previously only mode (1) was modeled, which meant traffic loss read
        0.000% almost permanently: the backbone topology is deliberately
        redundant and failures are capped at a handful of concurrent links,
        so a full source-destination disconnection essentially never
        happens. Counting congestion loss makes the SLO respond to actual
        simulated conditions instead of only a partition that never occurs.
        """
        volume = demand["volume_gbps"]
        if not result.get("path") or result.get("latency_ms") == float("inf"):
            return volume
        bottleneck = result.get("bottleneck_gbps")
        if bottleneck is None or bottleneck == float("inf"):
            return 0.0
        if bottleneck < volume:
            return volume - bottleneck
        return 0.0

    def measure_traffic_loss(self, demands: List[Dict[str, Any]], routed_results: List[Dict[str, Any]]) -> float:
        """
        Calculate and record traffic loss % for the current demand set. SLO: <= 0.1%.
        Loss is calculated as (lost volume / total volume) * 100.0, where lost
        volume covers both full outages and congestion above bottleneck
        capacity (see `_lost_volume_gbps`).
        """
        total_volume = sum(d["volume_gbps"] for d in demands)
        if total_volume == 0.0:
            self.traffic_loss_events.append(0.0)
            return 0.0

        unrouted_volume = sum(
            self._lost_volume_gbps(d, r) for d, r in zip(demands, routed_results)
        )

        loss_pct = (unrouted_volume / total_volume) * 100.0
        # Round to 3 decimal places
        loss_pct = round(loss_pct, 3)
        self.traffic_loss_events.append(loss_pct)
        return loss_pct

    def calculate_traffic_loss(self, demands: List[Dict[str, Any]], routed_results: List[Dict[str, Any]]) -> float:
        """Calculate current traffic loss (outage + congestion) without adding a historical sample."""
        total_volume = sum(d["volume_gbps"] for d in demands)
        if total_volume == 0.0:
            return 0.0

        unrouted_volume = sum(
            self._lost_volume_gbps(d, r) for d, r in zip(demands, routed_results)
        )

        return round((unrouted_volume / total_volume) * 100.0, 3)

    def calculate_path_optimality(self, routed_results: List[Dict[str, Any]], optimal_latencies: List[float]) -> float:
        """Calculate current path optimality without adding a historical sample."""
        if not routed_results:
            return 100.0

        optimal_count = 0
        for r, opt_lat in zip(routed_results, optimal_latencies):
            if (r["latency_ms"] == float('inf') and opt_lat == float('inf')) or (
                r["latency_ms"] != float('inf') and opt_lat != float('inf') and abs(r["latency_ms"] - opt_lat) < 1e-4
            ):
                optimal_count += 1

        return round((optimal_count / len(routed_results)) * 100.0, 1)

    def measure_path_optimality(self, routed_results: List[Dict[str, Any]], optimal_latencies: List[float]) -> float:
        """
        Calculate and record path optimality % compared to the true shortest path. SLO: >= 95%.
        Returns % of routes that match the optimal latency.
        """
        if not routed_results:
            self.path_optimality_scores.append(100.0)
            return 100.0
            
        optimal_count = 0
        for r, opt_lat in zip(routed_results, optimal_latencies):
            # If both are unreachable (inf) or their latencies match within precision
            if (r["latency_ms"] == float('inf') and opt_lat == float('inf')) or (
                r["latency_ms"] != float('inf') and opt_lat != float('inf') and abs(r["latency_ms"] - opt_lat) < 1e-4
            ):
                optimal_count += 1
                
        optimality_pct = (optimal_count / len(routed_results)) * 100.0
        optimality_pct = round(optimality_pct, 1)
        self.path_optimality_scores.append(optimality_pct)
        return optimality_pct

    def track_query_accuracy(self, is_correct: bool) -> None:
        """Track query accuracy vs NetworkX oracle to compute Availability (SLO >= 99.9%)."""
        self.total_queries += 1
        if is_correct:
            self.correct_queries += 1

    def report(self) -> Dict[str, Any]:
        """Generate final SLO metrics compliance report."""
        avg_conv = np.mean(self.convergence_times) if self.convergence_times else 0.0
        p95_conv = np.percentile(self.convergence_times, 95) if self.convergence_times else 0.0
        p99_conv = np.percentile(self.convergence_times, 99) if self.convergence_times else 0.0
        
        avg_loss = np.mean(self.traffic_loss_events) if self.traffic_loss_events else 0.0
        max_loss = max(self.traffic_loss_events) if self.traffic_loss_events else 0.0
        
        avg_opt = np.mean(self.path_optimality_scores) if self.path_optimality_scores else 100.0
        
        availability = (self.correct_queries / self.total_queries * 100.0) if self.total_queries > 0 else 100.0
        
        return {
            "avg_convergence_ms": round(float(avg_conv), 3),
            "p95_convergence_ms": round(float(p95_conv), 3),
            "p99_convergence_ms": round(float(p99_conv), 3),
            "convergence_slo_met": all(t <= 10.0 for t in self.convergence_times) if self.convergence_times else True,
            
            "avg_traffic_loss_pct": round(float(avg_loss), 3),
            "max_traffic_loss_pct": round(float(max_loss), 3),
            "traffic_loss_slo_met": all(l <= 0.1 for l in self.traffic_loss_events) if self.traffic_loss_events else True,
            
            "avg_path_optimality_pct": round(float(avg_opt), 1),
            "optimality_slo_met": all(s >= 95.0 for s in self.path_optimality_scores) if self.path_optimality_scores else True,
            
            "availability_pct": round(availability, 3),
            "availability_slo_met": availability >= 99.9
        }
