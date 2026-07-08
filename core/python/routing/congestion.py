"""
Congestion-aware routing for the ISP backbone.

The problem this solves ("many flows down the same road")
---------------------------------------------------------
The plain routing engine (routing.py) sends every demand down the *latency*
shortest path, ignoring how much traffic is already on a link. When many
high-volume demands share a hub link (Delhi–Mumbai etc.) that link's load can
exceed its capacity even with zero failures — that is congestion loss, and the
latency-only router does nothing to avoid it.

This module routes demands with LOAD-ADAPTIVE edge weights: as a link fills up,
its effective weight rises, so subsequent demands are naturally steered onto
alternate paths. This is exactly a stream of dynamic edge-reweight events — the
operation ADAPTSKEL is built to absorb — so congestion control and the dynamic
SSSP engine tell one story.

Two extra signals shape the weights:
  * utilisation  = load / capacity      (the real, current pressure on a link)
  * heat         = ADAPTSKEL heat score (how often the link is on chosen paths;
                   a forward-looking "this link is popular" prior)

Loss model
----------
Loss is measured on the WHOLE assignment, not per demand in isolation:
after every demand is placed, each link's overload = max(0, load - capacity)
is summed. That aggregate overload (plus any fully-unroutable demand) divided
by total offered volume is the congestion loss %. Spreading load reduces the
aggregate overload, which is the measurable win of congestion-aware routing.
"""
from __future__ import annotations

import heapq
from typing import Any, Dict, List, Optional, Set, Tuple

from .topology import BackboneTopology, Link

INF = float("inf")
Key = Tuple[int, int]


def _key(u: int, v: int) -> Key:
    return (min(u, v), max(u, v))


class CongestionAwareRouter:
    """
    Load-adaptive router over the backbone topology.

    Parameters
    ----------
    alpha : float
        Congestion penalty magnitude above the knee. A fully saturated link
        costs ~(1+alpha)x its base latency.
    beta : float
        Congestion penalty sharpness above the knee.
    gamma : float
        Weight of the ADAPTSKEL heat prior (0 disables heat influence).
    knee : float
        Utilisation below which a link costs exactly its base latency. Below
        the knee the effective weights equal the raw latencies, so the
        load-aware router routes IDENTICALLY to the latency-only baseline and
        only diverts flows once a link approaches saturation. This makes
        congestion-aware routing never worse than baseline when nothing is
        congested, and strictly better once links overload.
    """

    def __init__(
        self,
        topology: BackboneTopology,
        alpha: float = 10.0,
        beta: float = 3.0,
        gamma: float = 0.5,
        knee: float = 0.8,
    ) -> None:
        self.topology = topology
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.knee = knee
        self.links: Dict[Key, Link] = {
            _key(l.u, l.v): l for l in topology.links
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _healthy_adj(self, failed: Set[Key]) -> Dict[int, Dict[int, Link]]:
        """Adjacency of currently-healthy links: {node: {neighbour: Link}}."""
        adj: Dict[int, Dict[int, Link]] = {}
        for key, link in self.links.items():
            if key in failed:
                continue
            adj.setdefault(link.u, {})[link.v] = link
            adj.setdefault(link.v, {})[link.u] = link
        return adj

    def _eff_weight(self, link: Link, load: float, heat_norm: float) -> float:
        """Effective (congestion + heat aware) edge weight."""
        cap = link.capacity_gbps if link.capacity_gbps > 0 else 1.0
        util = load / cap
        # Hinge penalty: zero below the knee (identical to baseline weights),
        # rising steeply once a link approaches / exceeds capacity.
        over = max(0.0, util - self.knee)
        congestion = 1.0 + self.alpha * (over ** self.beta)
        # Heat prior only acts once a link is already under pressure (over>0),
        # so below the knee smart weights == baseline weights exactly. When a
        # link IS congested, its ADAPTSKEL heat (how popular it is) adds extra
        # cost so the busiest-and-hottest links shed load first.
        heat_term = 1.0 + (self.gamma * heat_norm if over > 0.0 else 0.0)
        return link.latency_ms * congestion * heat_term

    def _dijkstra(
        self,
        src: int,
        dst: int,
        adj: Dict[int, Dict[int, Link]],
        load: Dict[Key, float],
        heat_norm: Dict[Key, float],
    ) -> Optional[List[int]]:
        """Shortest path under current effective weights, or None if none."""
        if src == dst:
            return [src]
        dist: Dict[int, float] = {src: 0.0}
        prev: Dict[int, int] = {}
        pq: List[Tuple[float, int]] = [(0.0, src)]
        while pq:
            d, x = heapq.heappop(pq)
            if d > dist.get(x, INF):
                continue
            if x == dst:
                break
            for y, link in adj.get(x, {}).items():
                k = _key(x, y)
                w = self._eff_weight(link, load.get(k, 0.0), heat_norm.get(k, 0.0))
                nd = d + w
                if nd < dist.get(y, INF):
                    dist[y] = nd
                    prev[y] = x
                    heapq.heappush(pq, (nd, y))
        if dst not in dist:
            return None
        path = [dst]
        cur = dst
        while cur != src:
            cur = prev[cur]
            path.append(cur)
        path.reverse()
        return path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assign(
        self,
        demands: List[Dict[str, Any]],
        failed: Set[Key],
        heat: Optional[Dict[Key, int]] = None,
        load_aware: bool = True,
    ) -> Dict[str, Any]:
        """
        Place every demand on a path and report the resulting loss.

        load_aware=False routes every demand on the (heat-agnostic) latency
        shortest path — the baseline that ignores congestion. load_aware=True
        raises a link's weight as it fills, spreading traffic.
        """
        heat = heat or {}
        adj = self._healthy_adj(failed)

        hmax = max(heat.values(), default=0) or 1
        heat_norm: Dict[Key, float] = {k: v / hmax for k, v in heat.items()}
        # For the pure baseline, ignore both live load and heat prior.
        static_heat: Dict[Key, float] = heat_norm if load_aware else {}

        load: Dict[Key, float] = {}
        routed_volume = 0.0
        total_volume = 0.0

        for d in demands:
            vol = d["volume_gbps"]
            total_volume += vol
            live_load = load if load_aware else {}
            path = self._dijkstra(
                d["source"], d["destination"], adj, live_load, static_heat
            )
            if path is None:
                continue  # fully unroutable — whole demand lost (outage)
            routed_volume += vol
            for i in range(len(path) - 1):
                k = _key(path[i], path[i + 1])
                load[k] = load.get(k, 0.0) + vol

        # Aggregate congestion overload across all healthy links.
        overload = 0.0
        utilisation: Dict[str, float] = {}
        util_values: List[float] = []
        for key, link in self.links.items():
            if key in failed:
                continue
            lk = load.get(key, 0.0)
            over = lk - link.capacity_gbps
            if over > 0:
                overload += over
            u = lk / link.capacity_gbps
            utilisation[f"{key[0]}-{key[1]}"] = round(u, 3)
            util_values.append(u)

        lost = (total_volume - routed_volume) + overload
        loss_pct = 0.0 if total_volume == 0 else round(
            min(100.0, lost / total_volume * 100.0), 3
        )
        mean_util = sum(util_values) / len(util_values) if util_values else 0.0
        return {
            "loss_pct": loss_pct,
            "utilisation": utilisation,
            "max_utilisation": round(max(util_values, default=0.0), 3),
            "mean_utilisation": round(mean_util, 4),
            "routed_volume_gbps": round(routed_volume, 2),
            "total_volume_gbps": round(total_volume, 2),
        }

    @staticmethod
    def _scale_demands(
        demands: List[Dict[str, Any]], factor: float
    ) -> List[Dict[str, Any]]:
        """Return a copy of demands with volumes scaled by `factor`."""
        return [{**d, "volume_gbps": d["volume_gbps"] * factor} for d in demands]

    def compare(
        self,
        demands: List[Dict[str, Any]],
        failed: Set[Key],
        heat: Optional[Dict[Key, int]] = None,
        target_max_util: float = 0.85,
    ) -> Dict[str, Any]:
        """
        Baseline (latency-only) vs congestion-aware assignment on the same
        demand set. Returns both losses and the improvement — the demo number.

        Offered load is calibrated (uniformly scaled) so that on the HEALTHY
        backbone the busiest link sits at ~`target_max_util` (just under 1).
        The calibration deliberately uses the failure-free network, then that
        same scaled load is evaluated against the ACTUAL failure set. So:
          * healthy network  → busiest link ≈ 0.85 → ~0% loss for both routers,
          * link failures    → surviving links overload → baseline loses traffic,
            and congestion-aware routing spreads flows to lose less.
        Without this the Pareto generator offers far more than the backbone can
        carry and BOTH routers saturate at 100%, hiding the benefit.
        """
        probe = self.assign(demands, set(), heat, load_aware=False)  # healthy
        max_u = probe.get("max_utilisation", 0.0)
        factor = (target_max_util / max_u) if max_u > 1e-9 else 1.0
        dem = (
            self._scale_demands(demands, factor)
            if abs(factor - 1.0) > 1e-9
            else demands
        )

        base = self.assign(dem, failed, heat, load_aware=False)
        smart = self.assign(dem, failed, heat, load_aware=True)
        return {
            "baseline_loss_pct": base["loss_pct"],
            "congestion_aware_loss_pct": smart["loss_pct"],
            "improvement_pct": round(base["loss_pct"] - smart["loss_pct"], 3),
            "baseline_max_utilisation": base["max_utilisation"],
            "congestion_aware_max_utilisation": smart["max_utilisation"],
            "offered_load_scale": round(factor, 4),
        }
