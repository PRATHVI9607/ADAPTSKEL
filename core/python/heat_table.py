"""
Heat Table for ADAPTSKEL.

Maintains a rolling-window heat score for each edge.
Window size W: the last W queries are remembered.  Heat[e] = number of those
W queries whose path included edge e.

Promotion : heat[e] crosses T   (heat was T-1, now T)
Demotion  : heat[e] drops to T//2 (heat was T//2+1, now T//2)
"""

from __future__ import annotations

from collections import deque
from typing import NamedTuple


class Edge(NamedTuple):
    u: int
    v: int
    w: float


class HeatTable:
    """
    Rolling-window heat score tracking for edges.

    Parameters
    ----------
    W : int
        Window size (number of past queries remembered).
    T : int
        Promotion threshold.  An edge with heat >= T is "hot" and should
        live in F₁ (skeleton layer).  heat <= T//2 means it should be
        demoted back to F₂.
    """

    def __init__(self, W: int, T: int) -> None:
        self.W: int = W
        self.T: int = T
        self._T_half: int = T // 2

        # heat[canonical_key] = current heat score
        self._heat: dict[tuple[int, int], int] = {}

        # Circular window: each entry is a list of canonical edge keys queried
        # in that round.
        self._window: deque[list[tuple[int, int]]] = deque()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _key(u: int, v: int) -> tuple[int, int]:
        return (min(u, v), max(u, v))

    def _get(self, k: tuple[int, int]) -> int:
        return self._heat.get(k, 0)

    def _set(self, k: tuple[int, int], val: int) -> None:
        if val == 0:
            self._heat.pop(k, None)
        else:
            self._heat[k] = val

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def increment(self, path_edges: list[Edge]) -> list[Edge]:
        """
        Record a new query whose path used the given edges.

        Steps:
        1. Add the edge set to the window.
        2. Increment heat for each edge on the path.
        3. If the window is full (>W entries), evict the oldest.
        4. Return the list of edges that just became hot (heat crossed T).

        Returns
        -------
        newly_hot : list[Edge]
            Edges whose heat just reached T (were T-1 before this call).
        """
        keys = [self._key(e.u, e.v) for e in path_edges]
        path_map: dict[tuple[int, int], Edge] = {}
        for e, k in zip(path_edges, keys):
            path_map[k] = e

        # Record in window
        self._window.append(keys)

        newly_hot: list[Edge] = []
        for k in keys:
            old = self._get(k)
            new = old + 1
            self._set(k, new)
            if old < self.T <= new:
                newly_hot.append(path_map[k])

        # Evict if overflow — call evict here so the caller gets demotion list
        # but we return it as a side effect into a "cold" list accessible via
        # evict_oldest().  The caller should call evict_oldest() separately if
        # needed; here we only auto-evict silently to keep the window bounded.
        while len(self._window) > self.W:
            self._evict_one()

        return newly_hot

    def evict_oldest(self) -> list[Edge]:
        """
        Manually remove the oldest query from the window.
        Returns edges that just became cold (heat dropped to T//2).

        This is separated so the caller can decide when to trigger demotions.
        """
        if not self._window:
            return []
        return self._evict_one()

    def _evict_one(self) -> list[Edge]:
        """Remove the oldest window entry; return newly-cold edges."""
        if not self._window:
            return []
        old_keys = self._window.popleft()
        newly_cold: list[Edge] = []
        for k in old_keys:
            old = self._get(k)
            new = max(0, old - 1)
            self._set(k, new)
            # Edge becomes cold if heat just dropped to T//2
            # (was T//2 + 1, now T//2)
            if old == self._T_half + 1 and new == self._T_half:
                u, v = k
                newly_cold.append(Edge(u, v, 0.0))  # weight unknown at this layer
        return newly_cold

    def get(self, e: tuple[int, int]) -> int:
        """Return heat score for edge (u,v) (accepts either order)."""
        k = self._key(e[0], e[1])
        return self._get(k)

    def get_uv(self, u: int, v: int) -> int:
        """Return heat score for edge (u,v)."""
        return self._get(self._key(u, v))

    def set_heat(self, u: int, v: int, val: int) -> None:
        """Forcibly set the heat score for edge (u,v)."""
        k = self._key(u, v)
        self._set(k, max(0, val))

    def is_hot(self, u: int, v: int) -> bool:
        """True if heat[e] >= T (edge should be in F₁)."""
        return self._get(self._key(u, v)) >= self.T

    def should_demote(self, u: int, v: int) -> bool:
        """True if heat[e] <= T//2 (edge should leave F₁)."""
        return self._get(self._key(u, v)) <= self._T_half

    def all_scores(self) -> dict[tuple[int, int], int]:
        """Return a copy of all non-zero heat scores."""
        return dict(self._heat)

    def window_size(self) -> int:
        """Number of queries currently in the window."""
        return len(self._window)

    def update_threshold(self, T: int, W: int) -> None:
        """
        Update promotion/demotion thresholds when n changes.
        Does NOT retroactively evict — existing scores remain valid.
        """
        self.T = T
        self.W = W
        self._T_half = T // 2
