"""
Euler Tour Tree (ETT) / residual layer F₂ for ADAPTSKEL.

Uses a Union-Find (DSU) with rollback-free union-by-rank + path compression
for connectivity, plus a dict of edges organised by Holm et al. levels.

Guarantees:
  - add_edge / remove_edge : O(α(n)) amortised for DSU part; O(log n) for
    replacement search (small-to-large over component sets).
  - connected              : O(α(n))
  - min_crossing_edge      : O(k·log n) where k = smaller component size
  - raise_level            : amortised O(log²n) total over all raises per edge
  - get_component          : O(component size)
"""

from __future__ import annotations

from math import floor, log2
from typing import Optional


class _DSU:
    """
    Union-Find with union-by-size.
    Supports deletion by rebuilding when needed (simple reinitialization).
    """

    def __init__(self) -> None:
        self._parent: dict[int, int] = {}
        self._size: dict[int, int] = {}

    def add(self, v: int) -> None:
        if v not in self._parent:
            self._parent[v] = v
            self._size[v] = 1

    def find(self, v: int) -> int:
        # Path compression
        root = v
        while self._parent[root] != root:
            root = self._parent[root]
        # Compress
        cur = v
        while cur != root:
            nxt = self._parent[cur]
            self._parent[cur] = root
            cur = nxt
        return root

    def union(self, u: int, v: int) -> bool:
        """Union by size. Returns True if they were in different components."""
        ru, rv = self.find(u), self.find(v)
        if ru == rv:
            return False
        if self._size[ru] < self._size[rv]:
            ru, rv = rv, ru
        self._parent[rv] = ru
        self._size[ru] += self._size[rv]
        return True

    def connected(self, u: int, v: int) -> bool:
        return self.find(u) == self.find(v)

    def component_root(self, v: int) -> int:
        return self.find(v)

    def rebuild(self, vertices: list[int], spanning_edges: list[tuple[int, int]]) -> None:
        """Rebuild DSU from scratch given vertices and a set of tree edges."""
        self._parent = {v: v for v in vertices}
        self._size = {v: 1 for v in vertices}
        for u, v in spanning_edges:
            self.union(u, v)


class EulerTourForest:
    """
    Residual layer F₂ for ADAPTSKEL.

    Stores non-skeleton edges with Holm et al. levels in [0, max_level].
    Connectivity is maintained by a DSU over a spanning forest of F₂.

    Edge representation
    -------------------
    All edges keyed canonically as (min(u,v), max(u,v)).

    Level structure (Holm et al.)
    -----------------------------
    Each edge has a level in [0, L] where L = floor(log2(n)).
    Spanning-forest edges are in _forest_edges; non-tree edges in _non_tree_edges.
    Both dicts map  (u,v) -> {'w': weight, 'level': int}.

    Component tracking (for small-to-large)
    ----------------------------------------
    _comp_vertices[root] = set of vertex IDs in that component (DSU root keyed).
    Maintained lazily: after any structural change we call _rebuild_components().
    """

    def __init__(self) -> None:
        self._vertices: set[int] = set()

        # edge stores: canonical key -> {'w': float, 'level': int}
        self._forest_edges: dict[tuple[int, int], dict] = {}      # spanning tree
        self._non_tree_edges: dict[tuple[int, int], dict] = {}     # non-tree

        # adjacency: v -> set of canonical keys incident to v
        self._adj: dict[int, set[tuple[int, int]]] = {}

        self._dsu = _DSU()
        self._n: int = 0   # current vertex count (for max_level)

        # component vertex sets keyed by DSU root — rebuilt on demand
        self._comp_dirty: bool = True
        self._comp_vertices: dict[int, set[int]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _key(u: int, v: int) -> tuple[int, int]:
        return (min(u, v), max(u, v))

    def _ensure_vertex(self, v: int) -> None:
        if v not in self._vertices:
            self._vertices.add(v)
            self._dsu.add(v)
            self._adj[v] = set()
            self._n = len(self._vertices)
            self._comp_dirty = True

    def _add_adj(self, u: int, v: int) -> None:
        k = self._key(u, v)
        self._adj[u].add(k)
        self._adj[v].add(k)

    def _remove_adj(self, u: int, v: int) -> None:
        k = self._key(u, v)
        self._adj[u].discard(k)
        self._adj[v].discard(k)

    def _rebuild_dsu(self) -> None:
        """Rebuild DSU from the current spanning forest."""
        vlist = list(self._vertices)
        tree_edges = list(self._forest_edges.keys())
        self._dsu.rebuild(vlist, tree_edges)
        self._comp_dirty = True

    def _rebuild_components(self) -> None:
        """Rebuild _comp_vertices mapping DSU root -> vertex set."""
        self._comp_vertices = {}
        for v in self._vertices:
            r = self._dsu.find(v)
            if r not in self._comp_vertices:
                self._comp_vertices[r] = set()
            self._comp_vertices[r].add(v)
        self._comp_dirty = False

    def _get_comp(self, v: int) -> set[int]:
        if self._comp_dirty:
            self._rebuild_components()
        r = self._dsu.find(v)
        return self._comp_vertices.get(r, {v})

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def max_level(self) -> int:
        if self._n <= 1:
            return 0
        return max(0, floor(log2(self._n)))

    def add_vertex(self, v: int) -> None:
        self._ensure_vertex(v)

    def add_edge(self, u: int, v: int, w: float, level: int = 0) -> None:
        """
        Add edge (u,v,w) at the given Holm level.
        If u and v are in different components, the edge is added to the
        spanning forest; otherwise it becomes a non-tree edge.
        """
        self._ensure_vertex(u)
        self._ensure_vertex(v)
        k = self._key(u, v)

        # Deduplicate
        if k in self._forest_edges or k in self._non_tree_edges:
            return

        self._add_adj(u, v)

        if not self._dsu.connected(u, v):
            # Spanning tree edge
            self._forest_edges[k] = {"w": w, "level": level}
            self._dsu.union(u, v)
            self._comp_dirty = True
        else:
            # Non-tree edge
            self._non_tree_edges[k] = {"w": w, "level": level}

    def remove_edge(self, u: int, v: int) -> None:
        """
        Remove edge (u,v).  If it was a spanning-tree edge, find a replacement
        from non-tree edges (Holm et al. replacement search).
        """
        k = self._key(u, v)

        if k in self._non_tree_edges:
            del self._non_tree_edges[k]
            self._remove_adj(u, v)
            return

        if k not in self._forest_edges:
            return  # edge not present

        del self._forest_edges[k]
        self._remove_adj(u, v)

        # Rebuild DSU to reflect removal
        self._rebuild_dsu()

        # Try to find a replacement non-tree edge
        replacement = self._find_replacement(u, v)
        if replacement is not None:
            ru, rv, rw, rlev = replacement
            rk = self._key(ru, rv)
            # Move from non-tree to tree
            del self._non_tree_edges[rk]
            self._forest_edges[rk] = {"w": rw, "level": rlev}
            self._dsu.union(ru, rv)
            self._comp_dirty = True

    def _find_replacement(self, u: int, v: int) -> Optional[tuple[int, int, float, int]]:
        """
        Search for a non-tree edge that reconnects u's and v's components.
        Uses small-to-large: iterate the smaller component.
        Returns (u,v,w,level) tuple or None.
        """
        # After _rebuild_dsu, u and v are in separate components
        comp_u = self._get_comp(u)
        comp_v = self._get_comp(v)

        if len(comp_u) > len(comp_v):
            small, large = comp_v, comp_u
        else:
            small, large = comp_u, comp_v

        best: Optional[tuple[int, int, float, int]] = None
        best_w = float("inf")

        for node in small:
            for ek in list(self._adj[node]):
                eu, ev = ek
                data = self._non_tree_edges.get(ek)
                if data is None:
                    continue
                # Check if one endpoint is in small and the other in large
                other = ev if eu == node else eu
                # We need the other endpoint to be in a different component
                if not self._dsu.connected(node, other):
                    if data["w"] < best_w:
                        best_w = data["w"]
                        best = (eu, ev, data["w"], data["level"])

        return best

    def remove_edge_from_lct(self, u: int, v: int, w: float) -> None:
        """
        Called when an edge is removed from ETT because it's being promoted
        to the LCT (F₁).  Mirrors remove_edge but the edge was a forest edge
        in F₂ — treat it the same as remove_edge.
        """
        self.remove_edge(u, v)

    def connected(self, u: int, v: int) -> bool:
        """Return True if u and v are in the same F₂ component."""
        if u not in self._vertices or v not in self._vertices:
            return False
        return self._dsu.connected(u, v)

    def get_component(self, v: int) -> frozenset[int]:
        """Return frozenset of all vertex IDs in v's F₂ component."""
        if v not in self._vertices:
            return frozenset({v})
        return frozenset(self._get_comp(v))

    def min_crossing_edge(
        self,
        comp_u_root: int,
        comp_v_root: int,
        level: int,
    ) -> Optional[tuple[int, int, float]]:
        """
        Find the minimum-weight F₂ edge at the given level that crosses
        between the component of comp_u_root and comp_v_root.
        Returns (u, v, w) or None.
        """
        comp_u = self._get_comp(comp_u_root)
        comp_v = self._get_comp(comp_v_root)

        if len(comp_u) > len(comp_v):
            small, _ = comp_v, comp_u
        else:
            small, _ = comp_u, comp_v

        best: Optional[tuple[int, int, float]] = None
        best_w = float("inf")

        for node in small:
            for ek in self._adj[node]:
                eu, ev = ek
                # Check non-tree edges
                data = self._non_tree_edges.get(ek)
                if data is None:
                    data = self._forest_edges.get(ek)
                if data is None:
                    continue
                if data["level"] != level:
                    continue
                other = ev if eu == node else eu
                # One endpoint in comp_u, other in comp_v
                in_cu = node in comp_u
                in_cv = other in comp_v if in_cu else other in comp_u
                other_in_other = (other in comp_v) if (node in comp_u) else (other in comp_u)
                if other_in_other and data["w"] < best_w:
                    best_w = data["w"]
                    best = (eu, ev, data["w"])

        return best

    def raise_level(self, component_root: int, level: int) -> list[tuple[int, int, float]]:
        """
        Raise all level-`level` edges in the component to level+1.
        Returns the list of (u,v,w) edges that were raised.
        Amortised O(log²n) total per edge lifetime (Holm et al.).
        """
        comp = self._get_comp(component_root)
        raised: list[tuple[int, int, float]] = []

        for node in comp:
            for ek in list(self._adj[node]):
                eu, ev = ek
                for store in (self._forest_edges, self._non_tree_edges):
                    if ek in store and store[ek]["level"] == level:
                        store[ek]["level"] = level + 1
                        raised.append((eu, ev, store[ek]["w"]))

        return raised

    def get_edge_level(self, u: int, v: int) -> Optional[int]:
        k = self._key(u, v)
        data = self._forest_edges.get(k) or self._non_tree_edges.get(k)
        return data["level"] if data else None

    def get_edge_weight(self, u: int, v: int) -> Optional[float]:
        k = self._key(u, v)
        data = self._forest_edges.get(k) or self._non_tree_edges.get(k)
        return data["w"] if data else None

    def has_edge(self, u: int, v: int) -> bool:
        k = self._key(u, v)
        return k in self._forest_edges or k in self._non_tree_edges

    def all_edges(self) -> list[tuple[int, int, float, int]]:
        """Return all edges as (u, v, w, level)."""
        result: list[tuple[int, int, float, int]] = []
        for (u, v), d in self._forest_edges.items():
            result.append((u, v, d["w"], d["level"]))
        for (u, v), d in self._non_tree_edges.items():
            result.append((u, v, d["w"], d["level"]))
        return result

    def spanning_edges(self) -> list[tuple[int, int, float, int]]:
        """Return spanning forest edges."""
        return [(u, v, d["w"], d["level"]) for (u, v), d in self._forest_edges.items()]

    def n_edges(self) -> int:
        return len(self._forest_edges) + len(self._non_tree_edges)
