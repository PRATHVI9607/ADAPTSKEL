"""
Baseline SSSP implementations for benchmarking against ADAPTSKEL.

Provides:
  dijkstra()         — one-shot Dijkstra from source to a single target
  dijkstra_full()    — full SSSP from source (all reachable vertices)
  DijkstraBaseline   — stateful baseline that reruns Dijkstra on every query
"""

from __future__ import annotations

import heapq
from typing import Optional

import networkx as nx

INF = float("inf")


# ---------------------------------------------------------------------------
# Stateless helpers
# ---------------------------------------------------------------------------

def _build_adj(
    G_edges: dict[tuple[int, int], float]
) -> dict[int, list[tuple[int, float]]]:
    """Convert canonical-key edge dict to adjacency list."""
    adj: dict[int, list[tuple[int, float]]] = {}
    for (u, v), w in G_edges.items():
        adj.setdefault(u, []).append((v, w))
        adj.setdefault(v, []).append((u, w))
    return adj


def dijkstra(
    G_edges: dict[tuple[int, int], float],
    source: int,
    target: int,
) -> float:
    """
    Standard Dijkstra on a canonical-key edge dict.

    Parameters
    ----------
    G_edges : dict mapping (min(u,v), max(u,v)) -> weight
    source  : source vertex
    target  : target vertex

    Returns
    -------
    Shortest-path length, or INF if no path exists.
    """
    adj = _build_adj(G_edges)
    if source not in adj and source != target:
        return INF

    dist: dict[int, float] = {source: 0.0}
    heap: list[tuple[float, int]] = [(0.0, source)]

    while heap:
        d, u = heapq.heappop(heap)
        if u == target:
            return d
        if d > dist.get(u, INF):
            continue
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist.get(v, INF):
                dist[v] = nd
                heapq.heappush(heap, (nd, v))

    return dist.get(target, INF)


def dijkstra_full(
    G_edges: dict[tuple[int, int], float],
    source: int,
) -> dict[int, float]:
    """
    Full SSSP from source using Dijkstra.

    Parameters
    ----------
    G_edges : dict mapping canonical edge key -> weight
    source  : source vertex

    Returns
    -------
    dist : dict mapping reachable vertex -> shortest-path length
           Unreachable vertices are NOT included (caller should default to INF).
    """
    adj = _build_adj(G_edges)

    dist: dict[int, float] = {source: 0.0}
    heap: list[tuple[float, int]] = [(0.0, source)]

    while heap:
        d, u = heapq.heappop(heap)
        if d > dist.get(u, INF):
            continue
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist.get(v, INF):
                dist[v] = nd
                heapq.heappush(heap, (nd, v))

    return dist


# ---------------------------------------------------------------------------
# Stateful baseline — rerun Dijkstra on every mutation
# ---------------------------------------------------------------------------

class DijkstraBaseline:
    """
    Naive dynamic SSSP baseline.

    Strategy: store the graph in NetworkX; rerun single-source Dijkstra
    from `source` on every insert/delete; cache the result until the next
    mutation.

    This is O(m log n) per insertion/deletion, O(1) per query (cached).
    Used as the correctness oracle when comparing against AdaptSkel.
    """

    def __init__(self, source: int = 0) -> None:
        self.source: int = source
        self.G: nx.Graph = nx.Graph()
        self._dist_cache: dict[int, float] = {}
        self._cache_valid: bool = False

        # Statistics
        self._stats: dict[str, int] = {
            "insertions": 0,
            "deletions": 0,
            "queries": 0,
            "recomputes": 0,
        }

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_vertex(self, v: int) -> None:
        self.G.add_node(v)
        self._cache_valid = False

    def insert(self, u: int, v: int, w: float) -> None:
        """Add or update edge (u,v,w) and invalidate distance cache."""
        self.G.add_edge(u, v, weight=w)
        self._cache_valid = False
        self._stats["insertions"] += 1

    def delete(self, u: int, v: int) -> None:
        """Remove edge (u,v) if present, and invalidate distance cache."""
        if self.G.has_edge(u, v):
            self.G.remove_edge(u, v)
            self._cache_valid = False
        self._stats["deletions"] += 1

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def query(self, s: int, t: int) -> float:
        """
        Return δ(s, t).

        Always uses NetworkX Dijkstra from s directly.
        (Not cached by (s,t) pair because source may differ from self.source.)
        """
        self._stats["queries"] += 1
        try:
            return float(nx.shortest_path_length(self.G, s, t, weight="weight"))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return INF

    def sssp(self) -> dict[int, float]:
        """
        Return full SSSP distances from self.source to all reachable vertices.
        Caches the result until the next mutation.
        """
        if not self._cache_valid:
            self._recompute()
        return dict(self._dist_cache)

    def get_distance(self, v: int) -> float:
        """Return δ(source, v). Uses cache when valid."""
        if not self._cache_valid:
            self._recompute()
        return self._dist_cache.get(v, INF)

    def _recompute(self) -> None:
        """Rerun Dijkstra from self.source and cache."""
        self._stats["recomputes"] += 1
        try:
            lengths = nx.single_source_dijkstra_path_length(
                self.G, self.source, weight="weight"
            )
            self._dist_cache = dict(lengths)
        except nx.NodeNotFound:
            self._dist_cache = {}
        self._cache_valid = True

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        return dict(self._stats)

    def has_edge(self, u: int, v: int) -> bool:
        return self.G.has_edge(u, v)

    def n_vertices(self) -> int:
        return self.G.number_of_nodes()

    def n_edges(self) -> int:
        return self.G.number_of_edges()


# ---------------------------------------------------------------------------
# Incremental Bellman-Ford baseline (for negative-weight testing)
# ---------------------------------------------------------------------------

class BellmanFordBaseline:
    """
    Bellman-Ford baseline for graphs with potentially negative weights.
    O(nm) per recompute.  Not intended for performance comparison.
    """

    def __init__(self, source: int = 0) -> None:
        self.source: int = source
        self.G: nx.Graph = nx.Graph()

    def add_vertex(self, v: int) -> None:
        self.G.add_node(v)

    def insert(self, u: int, v: int, w: float) -> None:
        self.G.add_edge(u, v, weight=w)

    def delete(self, u: int, v: int) -> None:
        if self.G.has_edge(u, v):
            self.G.remove_edge(u, v)

    def query(self, s: int, t: int) -> float:
        try:
            return float(
                nx.bellman_ford_path_length(self.G, s, t, weight="weight")
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound, nx.NetworkXUnbounded):
            return INF

    def sssp(self) -> dict[int, float]:
        try:
            lengths = dict(
                nx.single_source_bellman_ford_path_length(
                    self.G, self.source, weight="weight"
                )
            )
            return lengths
        except (nx.NodeNotFound, nx.NetworkXUnbounded):
            return {}
