import time
from typing import List, Dict, Any, Tuple
import networkx as nx
from adaptskel import AdaptSkel
from routing.topology import BackboneTopology, Link

class RouteComputationEngine:
    """Uses AdaptSkel and NetworkX to compute optimal paths and capacity bottlenecks."""
    def __init__(self, adaptskel: AdaptSkel, topology: BackboneTopology) -> None:
        self.adaptskel = adaptskel
        self.topology = topology
        
        # Keep an active map of links: (min_id, max_id) -> Link
        self.active_links: Dict[Tuple[int, int], Link] = {}
        for link in topology.links:
            key = (min(link.u, link.v), max(link.u, link.v))
            self.active_links[key] = link

    def update_link_status(self, u: int, v: int, is_failed: bool) -> None:
        """Helper to sync link status with topology changes."""
        key = (min(u, v), max(u, v))
        if key in self.active_links:
            self.active_links[key].status = "failed" if is_failed else "healthy"

    def route(self, source: int, target: int) -> Dict[str, Any]:
        """Compute the shortest path path, latency, bottleneck capacity, and convergence time."""
        if source == target:
            return {
                "source": source,
                "destination": target,
                "path": [source],
                "latency_ms": 0.0,
                "bottleneck_gbps": float('inf'),
                "convergence_ms": 0.0
            }

        t0 = time.perf_counter()
        # Query AdaptSkel to update structures and retrieve shortest distance
        distance = self.adaptskel.query(source, target)
        query_time_ms = (time.perf_counter() - t0) * 1000.0
        
        # Reconstruct path using NetworkX mirror from adaptskel engine
        try:
            # self.adaptskel._G contains the active graph
            path = nx.shortest_path(self.adaptskel._G, source, target, weight="weight")
            
            # Compute bottleneck capacity
            bottleneck = float('inf')
            for i in range(len(path) - 1):
                u, v = path[i], path[i+1]
                key = (min(u, v), max(u, v))
                if key in self.active_links:
                    bottleneck = min(bottleneck, self.active_links[key].capacity_gbps)
                    
            return {
                "source": source,
                "destination": target,
                "path": path,
                "latency_ms": distance,
                "bottleneck_gbps": bottleneck if bottleneck != float('inf') else 0.0,
                "convergence_ms": query_time_ms
            }
        except (nx.NetworkXNoPath, nx.NodeNotFound, KeyError):
            return {
                "source": source,
                "destination": target,
                "path": [],
                "latency_ms": float('inf'),
                "bottleneck_gbps": 0.0,
                "convergence_ms": query_time_ms
            }
