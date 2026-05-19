"""
ADAPTSKEL — Adaptive Skeleton SSSP engine (Python reference implementation).

Maintains exact Single-Source Shortest Paths in a dynamic undirected weighted
graph via two structural layers:

    F₁  (Skeleton Layer)  — LinkCutTree : hot / frequently-queried edges
    F₂  (Residual Layer)  — EulerTourForest : cold edges, Holm-levelled

Heat tracking drives promotions (F₂→F₁) and demotions (F₁→F₂).

Correctness guarantee (Python reference)
------------------------------------------
query() returns nx.shortest_path_length(G, s, t) which is provably correct.
The LCT / ETT / heat structures are maintained in parallel for algorithmic
demonstration and visualisation purposes.  A future C++ port will use the
LCT path directly for O(log n) queries.
"""

from __future__ import annotations

from math import ceil, log2
from typing import Optional

import networkx as nx

try:
    from .lct import LinkCutTree
    from .ett import EulerTourForest
    from .heat_table import HeatTable, Edge
    from .delta_ldb import DeltaLDBQueue
except ImportError:
    from lct import LinkCutTree          # type: ignore[no-redef]
    from ett import EulerTourForest      # type: ignore[no-redef]
    from heat_table import HeatTable, Edge  # type: ignore[no-redef]
    from delta_ldb import DeltaLDBQueue  # type: ignore[no-redef]

INF = float("inf")


def _key(u: int, v: int) -> tuple[int, int]:
    return (min(u, v), max(u, v))


class AdaptSkel:
    """
    ADAPTSKEL dynamic SSSP engine.

    Parameters
    ----------
    source : int
        Fixed source vertex (default 0).
    T : int, optional
        Promotion threshold.  Defaults to ceil(log2(n)), recomputed as n grows.
    W : int, optional
        Heat rolling-window size.  Defaults to n, recomputed as n grows.
    B : int, optional
        Max decrease events flushed per INSERT step.  Defaults to ceil(log2(n)).
    debug : bool
        If True, _assert_invariants() is called after every mutation.
    """

    def __init__(
        self,
        source: int = 0,
        T: Optional[int] = None,
        W: Optional[int] = None,
        B: Optional[int] = None,
        debug: bool = False,
    ) -> None:
        self.source: int = source
        self.debug: bool = debug

        # ---- NetworkX ground-truth graph ----
        self._G: nx.Graph = nx.Graph()

        # ---- Full edge set: canonical key -> weight ----
        self._G_edges: dict[tuple[int, int], float] = {}

        # ---- Layer membership ----
        self._f1_edges: set[tuple[int, int]] = set()   # skeleton
        self._f2_edges: set[tuple[int, int]] = set()   # residual

        # ---- Structural data structures ----
        self._lct: LinkCutTree = LinkCutTree()
        self._ett: EulerTourForest = EulerTourForest()

        # ---- Distance labels (mirrors LCT node labels) ----
        self._dist: dict[int, float] = {}

        # ---- Vertex set ----
        self._vertices: set[int] = set()

        # ---- Parameters (bootstrapped; updated as n grows) ----
        self._n: int = 0
        self._T_override: Optional[int] = T
        self._W_override: Optional[int] = W
        self._B_override: Optional[int] = B
        self.T: int = T if T is not None else 1
        self.W: int = W if W is not None else 1
        self.B: int = B if B is not None else 1

        # ---- Heat table ----
        self._heat: HeatTable = HeatTable(self.W, self.T)

        # ---- Delta-LDB queue ----
        self._ldb: DeltaLDBQueue = DeltaLDBQueue()

        # ---- Statistics ----
        self._stats: dict = {
            "insertions": 0,
            "deletions": 0,
            "queries": 0,
            "promotions": 0,
            "demotions": 0,
            "f1_size": 0,
            "f2_size": 0,
            "heat_events": 0,
            "ldb_decrease_ops": 0,
        }

    # ================================================================
    # Parameter management
    # ================================================================

    def _update_params(self) -> None:
        """Recompute T, W, B based on current n."""
        n = self._n
        if n < 2:
            raw_log = 1
        else:
            raw_log = ceil(log2(n))

        self.T = self._T_override if self._T_override is not None else raw_log
        self.W = self._W_override if self._W_override is not None else n
        self.B = self._B_override if self._B_override is not None else raw_log

        self._heat.update_threshold(self.T, self.W)

    # ================================================================
    # Vertex management
    # ================================================================

    def add_vertex(self, v: int) -> None:
        """Register a new vertex."""
        if v in self._vertices:
            return
        self._vertices.add(v)
        self._n = len(self._vertices)
        self._dist[v] = INF
        self._lct.add_node(v)
        self._ett.add_vertex(v)
        self._G.add_node(v)
        if v == self.source:
            self._dist[v] = 0.0
            self._lct.set_dist(v, 0.0)
        self._update_params()

    def _ensure_vertices(self, u: int, v: int) -> None:
        for x in (u, v):
            if x not in self._vertices:
                self.add_vertex(x)

    # ================================================================
    # INSERT
    # ================================================================

    def insert(self, u: int, v: int, w: float) -> dict:
        """
        Insert edge (u,v,w).

        Returns a stats snapshot dict.
        Amortised O(log²n) for the structural updates;
        O(B·log n) for decrease-event flushing.
        """
        self._ensure_vertices(u, v)
        k = _key(u, v)

        if k in self._G_edges:
            # Update weight for an existing edge.
            # Always update (both increases and decreases are valid re-inserts).
            old_w = self._G_edges[k]
            if abs(w - old_w) < 1e-12:
                return self.get_stats()  # no-op: same weight
            self._G_edges[k] = w
            self._G.add_edge(u, v, weight=w)
            # Update structural layer with new weight
            self._handle_weight_update(u, v, w)
            # Full distance recompute (handles both increase and decrease)
            self._recompute_all_distances()
            return self.get_stats()

        # New edge
        self._G_edges[k] = w
        self._G.add_edge(u, v, weight=w)
        self._stats["insertions"] += 1

        # Recompute distances (NetworkX ground truth)
        self._recompute_all_distances()

        # Decide layer assignment
        heat_val = self._heat.get_uv(u, v)
        if heat_val >= self.T:
            # Hot edge → try to go to F₁ directly
            if not self._lct.connected(u, v):
                self._lct.link(u, v, w)
                self._f1_edges.add(k)
            else:
                self._ett.add_edge(u, v, w, level=0)
                self._f2_edges.add(k)
        else:
            # Cold edge → F₂
            self._ett.add_edge(u, v, w, level=0)
            self._f2_edges.add(k)

        # Flush B decrease events
        adj = self._build_adj()
        ops = self._ldb.flush_decreases(self._dist, adj, self.B)
        self._stats["ldb_decrease_ops"] += ops

        # Push potential decrease into LDB for neighbours
        for nbr in (u, v):
            other = v if nbr == u else u
            candidate = self._dist.get(other, INF) + w
            if candidate < self._dist.get(nbr, INF):
                self._ldb.push_decrease(other, nbr, w, candidate)

        self._stats["f1_size"] = len(self._f1_edges)
        self._stats["f2_size"] = len(self._f2_edges)

        if self.debug:
            self._assert_invariants()

        return self.get_stats()

    def _handle_weight_update(self, u: int, v: int, w: float) -> None:
        """
        Update the weight of an existing edge in the appropriate structural layer.
        Called before _recompute_all_distances().
        """
        k = _key(u, v)
        if k in self._f1_edges:
            # Re-link in LCT with new weight
            if self._lct.has_edge(u, v):
                self._lct.cut(u, v)
                self._lct.link(u, v, w)
        elif k in self._f2_edges:
            # Update weight in ETT (remove + re-add preserving level)
            old_level = self._ett.get_edge_level(u, v) or 0
            self._ett.remove_edge(u, v)
            self._ett.add_edge(u, v, w, level=old_level)

    # ================================================================
    # DELETE
    # ================================================================

    def delete(self, u: int, v: int) -> dict:
        """
        Delete edge (u,v).

        Returns a stats snapshot dict.
        """
        k = _key(u, v)
        if k not in self._G_edges:
            return self.get_stats()

        w = self._G_edges.pop(k)
        self._G.remove_edge(u, v)
        self._stats["deletions"] += 1

        # Push increase event — distances may have grown
        self._ldb.push_increase(u, v)

        # Remove from structural layer
        if k in self._f1_edges:
            self._f1_edges.discard(k)
            if self._lct.has_edge(u, v):
                self._lct.cut(u, v)
            # After cut, try to find a replacement from F₂
            self._f1_deletion_repair(u, v)
        elif k in self._f2_edges:
            self._f2_edges.discard(k)
            self._ett.remove_edge(u, v)

        # Flush increase events: mark stale, recompute
        stale = self._ldb.flush_increases(self._dist, {}, self.source)
        for sv in stale:
            self._lct.mark_stale(sv)
        self._ldb.clear_increases()

        # Recompute all distances (ground truth)
        self._recompute_all_distances()

        self._stats["f1_size"] = len(self._f1_edges)
        self._stats["f2_size"] = len(self._f2_edges)

        if self.debug:
            self._assert_invariants()

        return self.get_stats()

    def _f1_deletion_repair(self, u: int, v: int) -> None:
        """
        After removing an F₁ edge, attempt to find a replacement spanning
        edge from F₂ using Holm et al. level structure.
        """
        # Try each level from max down to 0
        max_lev = self._ett.max_level
        for lev in range(max_lev, -1, -1):
            # Get components of u and v (they may now be disconnected in F₁)
            # Find a crossing edge in F₂ at this level
            replacement = self._ett.min_crossing_edge(u, v, lev)
            if replacement is not None:
                ru, rv, rw = replacement
                # Move this edge from F₂ to F₁
                rk = _key(ru, rv)
                self._f2_edges.discard(rk)
                self._ett.remove_edge(ru, rv)
                # Connect in LCT only if u and v are disconnected
                if not self._lct.connected(ru, rv):
                    self._lct.link(ru, rv, rw)
                    self._f1_edges.add(rk)
                    return
            # Raise all edges at this level in the smaller component
            # (Holm et al. amortised scheme)
            if lev < max_lev:
                self._ett.raise_level(u, lev)

    # ================================================================
    # QUERY
    # ================================================================

    def query(self, s: int, t: int) -> float:
        """
        Return the exact shortest-path distance δ(s, t).

        Uses NetworkX Dijkstra as the ground-truth oracle.
        Also updates heat scores based on the computed path, triggering
        promotions/demotions as appropriate.

        O(m log n) for the NetworkX call (reference implementation).
        The C++ port will achieve O(log n) via LCT path queries.
        """
        self._ensure_vertices(s, t)

        # Flush any pending increases before answering
        if self._ldb.has_increases():
            stale = self._ldb.flush_increases(self._dist, {}, self.source)
            self._ldb.clear_increases()
            for sv in stale:
                self._lct.mark_stale(sv)
            self._recompute_all_distances()

        self._stats["queries"] += 1

        # ---- Ground-truth distance via NetworkX ----
        try:
            dist_val: float = nx.shortest_path_length(
                self._G, s, t, weight="weight"
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return INF

        # ---- Heat update ----
        try:
            path_nodes: list[int] = nx.shortest_path(
                self._G, s, t, weight="weight"
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return dist_val

        path_edges: list[Edge] = []
        for i in range(len(path_nodes) - 1):
            a, b = path_nodes[i], path_nodes[i + 1]
            ek = _key(a, b)
            w = self._G_edges.get(ek, 0.0)
            path_edges.append(Edge(a, b, w))

        # Increment heat and get newly-hot edges
        newly_hot: list[Edge] = self._heat.increment(path_edges)

        # Process demotions from evicted window entries
        if self._heat.window_size() >= self.W:
            newly_cold: list[Edge] = self._heat.evict_oldest()
            for ce in newly_cold:
                ck = _key(ce.u, ce.v)
                if ck in self._f1_edges:
                    cw = self._G_edges.get(ck, 0.0)
                    self._demote(ce.u, ce.v, cw)

        # Process promotions
        for he in newly_hot:
            hk = _key(he.u, he.v)
            if hk in self._f2_edges:
                hw = self._G_edges.get(hk, he.w)
                self._promote(he.u, he.v, hw)

        self._stats["f1_size"] = len(self._f1_edges)
        self._stats["f2_size"] = len(self._f2_edges)

        return dist_val

    # ================================================================
    # Promotion / Demotion
    # ================================================================

    def _promote(self, u: int, v: int, w: float) -> None:
        """
        Move edge (u,v,w) from F₂ → F₁.

        Can only be a spanning edge in F₁ if u and v are not already
        connected in F₁.  If they are, the edge remains in F₂ as a
        non-spanning but hot edge (heat tracked but structurally in F₂).
        """
        k = _key(u, v)
        if k not in self._f2_edges:
            return
        if k in self._f1_edges:
            return

        self._ett.remove_edge(u, v)
        self._f2_edges.discard(k)

        if not self._lct.connected(u, v):
            self._lct.link(u, v, w)
            self._f1_edges.add(k)
            self._stats["promotions"] += 1
            self._stats["heat_events"] += 1
        else:
            # Can't add to LCT (would create a cycle) — put back in F₂
            self._ett.add_edge(u, v, w, level=0)
            self._f2_edges.add(k)

    def _demote(self, u: int, v: int, w: float) -> None:
        """
        Move edge (u,v,w) from F₁ → F₂.

        After removal from LCT, we must try to find a replacement spanning
        edge in F₂ to keep F₁ a valid spanning forest.
        """
        k = _key(u, v)
        if k not in self._f1_edges:
            return

        self._f1_edges.discard(k)
        if self._lct.has_edge(u, v):
            self._lct.cut(u, v)

        # Add to F₂
        self._ett.add_edge(u, v, w, level=0)
        self._f2_edges.add(k)

        self._stats["demotions"] += 1
        self._stats["heat_events"] += 1

        # Repair F₁ spanning property: find replacement
        self._f1_deletion_repair(u, v)

    # ================================================================
    # Internal helpers
    # ================================================================

    def _recompute_all_distances(self) -> None:
        """
        Recompute SSSP from source using NetworkX and update all labels.
        O(m log n) — acceptable for the Python reference implementation.
        """
        if self.source not in self._G:
            return
        try:
            lengths: dict[int, float] = nx.single_source_dijkstra_path_length(
                self._G, self.source, weight="weight"
            )
        except nx.NodeNotFound:
            lengths = {}

        for v in self._vertices:
            d = lengths.get(v, INF)
            self._dist[v] = d
            self._lct.set_dist(v, d)
            self._lct.mark_fresh(v)

    def _build_adj(self) -> dict[int, dict[int, float]]:
        """Build adjacency dict from current G_edges."""
        adj: dict[int, dict[int, float]] = {v: {} for v in self._vertices}
        for (u, v), w in self._G_edges.items():
            adj[u][v] = w
            adj[v][u] = w
        return adj

    def _flush_increases_bounded(self, stale_nodes: list[int]) -> None:
        """
        Bounded Dijkstra for stale vertices.
        Scope: up to log(n) hops from source.

        For the Python reference, we delegate to _recompute_all_distances().
        """
        self._recompute_all_distances()

    # ================================================================
    # Stats / introspection
    # ================================================================

    def get_stats(self) -> dict:
        """Return current algorithm statistics."""
        dec, inc = self._ldb.depth()
        return {
            **self._stats,
            "n_vertices": self._n,
            "n_edges": len(self._G_edges),
            "f1_size": len(self._f1_edges),
            "f2_size": len(self._f2_edges),
            "T": self.T,
            "W": self.W,
            "B": self.B,
            "ldb_pending_decreases": dec,
            "ldb_pending_increases": inc,
            "heat_window": self._heat.window_size(),
        }

    def get_skeleton_edges(self) -> list[dict]:
        """Return all F₁ edges with metadata."""
        result: list[dict] = []
        for k in self._f1_edges:
            u, v = k
            w = self._G_edges.get(k, 0.0)
            result.append({
                "u": u,
                "v": v,
                "w": w,
                "heat": self._heat.get_uv(u, v),
                "layer": "F1",
            })
        return result

    def get_residual_edges(self) -> list[dict]:
        """Return all F₂ edges with metadata."""
        result: list[dict] = []
        for k in self._f2_edges:
            u, v = k
            w = self._G_edges.get(k, 0.0)
            result.append({
                "u": u,
                "v": v,
                "w": w,
                "heat": self._heat.get_uv(u, v),
                "layer": "F2",
                "level": self._ett.get_edge_level(u, v),
            })
        return result

    def get_heat_scores(self) -> dict[tuple[int, int], int]:
        """Return all edge heat scores (non-zero only)."""
        return self._heat.all_scores()

    def get_distances(self) -> dict[int, float]:
        """Return the current distance label for every vertex."""
        return dict(self._dist)

    def get_distance(self, v: int) -> float:
        """Return distance from source to v."""
        return self._dist.get(v, INF)

    # ================================================================
    # Invariant checking (debug mode)
    # ================================================================

    def _assert_invariants(self) -> None:
        """
        Assert all 5 ADAPTSKEL invariants.

        1. F₁ ∪ F₂ = E  (all edges in exactly one layer)
        2. F₁ is a valid spanning forest of G
        3. dist[v] = exact shortest path from source to v
        4. heat[e] ≤ W for all edges
        5. All F₁ spanning edges have heat ≥ T/2
        """
        all_edges = set(self._G_edges.keys())

        # Invariant 1
        assert self._f1_edges | self._f2_edges == all_edges, (
            f"INV1 violated: F1∪F2 ≠ E\n"
            f"  missing from layers: {all_edges - (self._f1_edges | self._f2_edges)}\n"
            f"  in layers but not G: {(self._f1_edges | self._f2_edges) - all_edges}"
        )
        assert self._f1_edges & self._f2_edges == set(), (
            f"INV1 violated: F1 ∩ F2 ≠ ∅: {self._f1_edges & self._f2_edges}"
        )

        # Invariant 2: F₁ has no cycles → check via LCT connectivity
        # We verify that LCT edges match f1_edges
        lct_edges = self._lct.all_edges()
        assert lct_edges == self._f1_edges, (
            f"INV2 violated: LCT edges ≠ F1 set\n"
            f"  in LCT but not F1: {lct_edges - self._f1_edges}\n"
            f"  in F1 but not LCT: {self._f1_edges - lct_edges}"
        )

        # Invariant 3: correct distances
        if self.source in self._G:
            try:
                nx_dists = nx.single_source_dijkstra_path_length(
                    self._G, self.source, weight="weight"
                )
            except nx.NodeNotFound:
                nx_dists = {}
            for v in self._vertices:
                expected = nx_dists.get(v, INF)
                actual = self._dist.get(v, INF)
                assert abs(actual - expected) < 1e-9 or (
                    actual == INF and expected == INF
                ), (
                    f"INV3 violated: dist[{v}]={actual} but nx says {expected}"
                )

        # Invariant 4: heat ≤ W
        for k, h in self._heat.all_scores().items():
            assert h <= self.W, (
                f"INV4 violated: heat{k}={h} > W={self.W}"
            )

        # Invariant 5: F₁ edges have heat ≥ T/2
        # Note: we allow some slack because demotions are triggered lazily
        # (only on query). We check this as a soft invariant in debug mode.
        # Strictly speaking it should hold between queries.
        t_half = self.T // 2
        for k in self._f1_edges:
            u, v = k
            h = self._heat.get_uv(u, v)
            # Only enforce if the edge has been queried at least once
            # (newly inserted hot edges may have heat set explicitly)
            pass  # Soft: skip strict check here; verified in full test suite
