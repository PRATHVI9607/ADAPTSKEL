"""
Delta-LDB (Lazy Distance Batching) Queue for ADAPTSKEL.

Separates two kinds of distance update events:

DECREASE events
  Arise from edge insertions.  They are safe to defer because the current
  distance labels are pessimistic upper-bounds; queries can be answered
  optimistically from the current label without correctness risk when the
  AdaptSkel engine uses nx.shortest_path_length as the ground truth.
  Stored as a min-heap ordered by (−improvement, new_dist) so we process the
  most beneficial relaxations first.

INCREASE events
  Arise from edge deletions.  Distance labels may now be too small (stale).
  They MUST be flushed before any distance query is answered.
  Stored as a min-heap of (current_dist, u, v) — not currently sorted by
  priority; we just drain the whole set before queries.
"""

from __future__ import annotations

import heapq
from typing import Optional


class DeltaLDBQueue:
    """
    Lazy Distance Label Batching.

    Separates DECREASE events (from insertions — non-urgent, safe to defer)
    from INCREASE events (from deletions — must flush before query).
    """

    def __init__(self) -> None:
        # min-heap entries: (new_dist, u, v, w)
        # We want to process smallest new_dist first (closest vertices first,
        # mimicking Dijkstra relaxation order).
        self._decrease: list[tuple[float, int, int, float]] = []
        self._increase: list[tuple[float, int, int]] = []  # (old_dist, u, v)

        self._pending_decreases: int = 0
        self._pending_increases: int = 0

        # Lazy deletion sets — entries that have been superseded
        self._decrease_invalid: set[tuple[int, int, float, float]] = set()
        self._increase_invalid: set[tuple[int, int]] = set()

    # ------------------------------------------------------------------
    # Push operations
    # ------------------------------------------------------------------

    def push_decrease(
        self, u: int, v: int, w: float, new_dist: float
    ) -> None:
        """
        Queue a DECREASE event.

        Edge (u → v) with weight w might improve v's distance to new_dist
        (= dist[u] + w).  We enqueue by new_dist so that closer vertices
        (small new_dist) are processed first, consistent with Dijkstra order.
        """
        entry = (new_dist, u, v, w)
        heapq.heappush(self._decrease, entry)
        self._pending_decreases += 1

    def push_increase(self, u: int, v: int) -> None:
        """
        Queue an INCREASE event: edge (u,v) was deleted; distances may
        have grown.  We record both endpoints as potentially stale.
        """
        for x in (u, v):
            entry = (0.0, u, x)  # priority unused; we drain all increases
            heapq.heappush(self._increase, entry)
        self._pending_increases += 1

    # ------------------------------------------------------------------
    # Flush operations
    # ------------------------------------------------------------------

    def flush_decreases(
        self,
        dist: dict[int, float],
        adj: dict[int, dict[int, float]],
        limit: int,
    ) -> int:
        """
        Process up to `limit` decrease events via edge relaxation.

        Parameters
        ----------
        dist : dict mapping vertex -> current distance label (mutated in place)
        adj  : adjacency dict  {u: {v: w, ...}, ...}
        limit: max number of relaxation steps to perform (B = ceil(log2 n))

        Returns
        -------
        ops : number of relaxation steps actually performed
        """
        ops = 0
        while self._decrease and ops < limit:
            new_dist, u, v, w = heapq.heappop(self._decrease)
            self._pending_decreases = max(0, self._pending_decreases - 1)

            # Stale check: if the tentative distance is no longer an improvement
            # (someone else already relaxed v to something ≤ new_dist), skip.
            current_v = dist.get(v, float("inf"))
            if new_dist >= current_v:
                continue  # already dominated

            # Check u's distance hasn't changed (if dist[u] increased, this
            # relaxation is invalid).
            current_u = dist.get(u, float("inf"))
            if current_u + w > new_dist + 1e-12:
                continue  # u's label got worse; skip

            # Relaxation is valid
            dist[v] = new_dist
            ops += 1

            # Propagate: push new relaxations for v's neighbours
            for nb, edge_w in adj.get(v, {}).items():
                candidate = new_dist + edge_w
                if candidate < dist.get(nb, float("inf")):
                    self.push_decrease(v, nb, edge_w, candidate)

        return ops

    def flush_increases(
        self,
        dist: dict[int, float],
        adj: dict[int, dict[int, float]],
        source: int,
    ) -> set[int]:
        """
        Drain all INCREASE events and return the set of stale vertices.

        For the Python reference implementation, we do NOT recompute distances
        here — the caller (AdaptSkel) delegates to NetworkX for correctness.
        We simply return the set of affected vertices so the engine can mark
        them stale and recompute.
        """
        stale: set[int] = set()
        while self._increase:
            _, u, v = heapq.heappop(self._increase)
            stale.add(u)
            stale.add(v)
        self._pending_increases = 0
        return stale

    # ------------------------------------------------------------------
    # Predicates / introspection
    # ------------------------------------------------------------------

    def has_increases(self) -> bool:
        """True if there are unflushed INCREASE events."""
        return bool(self._increase)

    def has_decreases(self) -> bool:
        """True if there are queued DECREASE events."""
        return bool(self._decrease)

    def depth(self) -> tuple[int, int]:
        """Returns (pending_decreases, pending_increases)."""
        return (self._pending_decreases, self._pending_increases)

    def clear_increases(self) -> None:
        """Discard all pending INCREASE events (called after a full recompute)."""
        self._increase.clear()
        self._pending_increases = 0

    def clear_decreases(self) -> None:
        """Discard all pending DECREASE events."""
        self._decrease.clear()
        self._pending_decreases = 0

    def clear_all(self) -> None:
        self.clear_increases()
        self.clear_decreases()

    def peek_min_decrease(self) -> Optional[tuple[float, int, int, float]]:
        """
        Return the top decrease event without popping it.
        Returns None if queue is empty.
        """
        return self._decrease[0] if self._decrease else None
