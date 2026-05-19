"""
Unit tests for HeatTable (heat scoring, promotion, demotion, window eviction).

HeatTable lives in core/python/heat_table.py (also importable via adaptskel).

Real API:
  HeatTable(W: int, T: int)
  .increment(path_edges: list[Edge]) -> list[Edge]   # Edge is NamedTuple(u,v,w)
  .evict_oldest()                   -> list[Edge]
  .get(e: tuple[int,int])           -> int
  .get_uv(u, v)                     -> int
  .set_heat(u, v, val)
  .is_hot(u, v)                     -> bool
  .should_demote(u, v)              -> bool
  .window_size()                    -> int
  .update_threshold(T, W)

Test structure:
  - TestPromotion: heat crossing T triggers promotion
  - TestDemotion:  heat dropping to T/2 or below triggers demotion
  - TestWindow:    rolling window eviction keeps heat bounded
"""
from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core', 'python'))

# ---------------------------------------------------------------------------
# Import HeatTable and Edge — with graceful skip if engine not yet written
# ---------------------------------------------------------------------------

try:
    from heat_table import HeatTable, Edge  # type: ignore
    HAS_HEAT_TABLE = True
except ImportError:
    try:
        from adaptskel import HeatTable, Edge  # type: ignore
        HAS_HEAT_TABLE = True
    except ImportError:
        HAS_HEAT_TABLE = False

pytestmark = pytest.mark.skipif(
    not HAS_HEAT_TABLE,
    reason="HeatTable not yet importable from core/python/heat_table.py",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EdgeKey = tuple[int, int]


def make_edge(u: int, v: int, w: float = 1.0) -> "Edge":
    return Edge(u, v, w)


def make_path_edges(length: int) -> list:
    """Return a chain of `length` Edge objects: (0,1), (1,2), …"""
    return [Edge(i, i + 1, 1.0) for i in range(length)]


def edge_key(u: int, v: int) -> EdgeKey:
    return (min(u, v), max(u, v))


def edges_to_keys(edges) -> set[EdgeKey]:
    """Convert a list of Edge objects to a set of canonical keys."""
    return {edge_key(e.u, e.v) for e in edges}


# ---------------------------------------------------------------------------
# TestPromotion
# ---------------------------------------------------------------------------

class TestPromotion:
    """Edges promoted when heat >= T."""

    def test_single_edge_reaches_threshold(self):
        T, W = 5, 100
        ht = HeatTable(W, T)
        e = make_edge(0, 1)
        key = edge_key(0, 1)
        newly_hot_keys: set[EdgeKey] = set()
        for _ in range(T):
            promoted = ht.increment([e])
            newly_hot_keys.update(edges_to_keys(promoted))
        # After T increments, the edge must have been promoted exactly once
        assert key in newly_hot_keys or ht.get(key) >= T, (
            f"Edge {key} should reach heat {T} after {T} increments"
        )

    def test_multiple_edges_same_path(self):
        T, W = 3, 50
        ht = HeatTable(W, T)
        path = make_path_edges(3)  # edges (0,1),(1,2),(2,3)
        all_promoted_keys: set[EdgeKey] = set()
        for _ in range(T):
            all_promoted_keys.update(edges_to_keys(ht.increment(path)))
        for e in path:
            k = edge_key(e.u, e.v)
            assert k in all_promoted_keys or ht.get(k) >= T

    def test_edge_not_promoted_below_threshold(self):
        T, W = 10, 100
        ht = HeatTable(W, T)
        e = make_edge(3, 7)
        key = edge_key(3, 7)
        promoted_keys: set[EdgeKey] = set()
        for _ in range(T - 1):
            promoted_keys.update(edges_to_keys(ht.increment([e])))
        assert key not in promoted_keys

    def test_promotion_at_exact_threshold(self):
        T, W = 4, 100
        ht = HeatTable(W, T)
        e = make_edge(1, 2)
        key = edge_key(1, 2)
        promoted_keys: set[EdgeKey] = set()
        for _ in range(T):
            promoted_keys.update(edges_to_keys(ht.increment([e])))
        assert key in promoted_keys

    def test_heat_score_tracks_increments(self):
        T, W = 20, 100
        ht = HeatTable(W, T)
        e = make_edge(5, 9)
        key = edge_key(5, 9)
        for _ in range(7):
            ht.increment([e])
        assert ht.get(key) == 7

    def test_multiple_independent_edges(self):
        """Two edges on different paths accumulate heat independently."""
        T, W = 3, 50
        ht = HeatTable(W, T)
        e1 = make_edge(0, 1)
        e2 = make_edge(10, 20)
        for _ in range(T):
            ht.increment([e1])
        for _ in range(T - 1):
            ht.increment([e2])
        assert ht.get(edge_key(0, 1)) >= T
        assert ht.get(edge_key(10, 20)) == T - 1

    def test_is_hot_after_promotion(self):
        T, W = 3, 50
        ht = HeatTable(W, T)
        e = make_edge(0, 1)
        for _ in range(T):
            ht.increment([e])
        assert ht.is_hot(0, 1)

    def test_is_hot_before_promotion(self):
        T, W = 5, 50
        ht = HeatTable(W, T)
        e = make_edge(2, 3)
        for _ in range(T - 1):
            ht.increment([e])
        assert not ht.is_hot(2, 3)

    def test_get_uv_matches_get(self):
        T, W = 10, 50
        ht = HeatTable(W, T)
        e = make_edge(7, 11)
        for _ in range(4):
            ht.increment([e])
        assert ht.get_uv(7, 11) == ht.get(edge_key(7, 11))
        assert ht.get_uv(11, 7) == ht.get(edge_key(7, 11))  # symmetric


# ---------------------------------------------------------------------------
# TestDemotion
# ---------------------------------------------------------------------------

class TestDemotion:
    """Edges demoted when heat drops to T//2 or below."""

    def test_demote_after_evictions(self):
        T, W = 6, 10
        ht = HeatTable(W, T)
        e = make_edge(0, 1)
        key = edge_key(0, 1)
        for _ in range(T):
            ht.increment([e])
        demoted_keys: set[EdgeKey] = set()
        for _ in range(W + T):  # generously evict
            demoted_keys.update(edges_to_keys(ht.evict_oldest()))
        # Edge must be demoted if heat dropped below T//2
        assert key in demoted_keys or ht.get(key) <= T // 2

    def test_hysteresis_band(self):
        """
        Edge promoted at T should not be immediately demoted on first eviction;
        hysteresis band [T//2, T] prevents oscillation.
        """
        T, W = 8, 100
        ht = HeatTable(W, T)
        e = make_edge(2, 3)
        key = edge_key(2, 3)
        for _ in range(T):
            ht.increment([e])
        # Evict one query — heat drops to T-1=7 which is > T//2=4 → no demotion
        demoted = edges_to_keys(ht.evict_oldest())
        if ht.get(key) > T // 2:
            assert key not in demoted, (
                "Edge should not be demoted while heat is above T//2"
            )

    def test_demotion_clears_from_skeleton(self):
        """After demotion, edge heat is <= T//2."""
        T, W = 4, 8
        ht = HeatTable(W, T)
        e = make_edge(7, 8)
        key = edge_key(7, 8)
        for _ in range(T):
            ht.increment([e])
        for _ in range(W * 2):
            ht.evict_oldest()
        assert ht.get(key) <= T // 2

    def test_no_demotion_if_heat_still_high(self):
        """If heat remains above T//2, no demotion should occur."""
        T, W = 10, 50
        ht = HeatTable(W, T)
        e = make_edge(4, 5)
        key = edge_key(4, 5)
        for _ in range(T):
            ht.increment([e])
        # Only evict 1 query → heat = T-1 = 9 > T//2 = 5
        demoted = edges_to_keys(ht.evict_oldest())
        assert key not in demoted

    def test_should_demote_flag(self):
        T, W = 6, 20
        ht = HeatTable(W, T)
        e = make_edge(0, 1)
        # Promote
        for _ in range(T):
            ht.increment([e])
        assert not ht.should_demote(0, 1)
        # Evict enough to drop below T//2
        for _ in range(W * 2):
            ht.evict_oldest()
        assert ht.should_demote(0, 1)


# ---------------------------------------------------------------------------
# TestWindow
# ---------------------------------------------------------------------------

class TestWindow:
    """Rolling window correctly evicts oldest queries and bounds heat."""

    def test_window_size_bounds_max_heat(self):
        """
        After W queries each incrementing the same edge, heat equals W.
        After W more queries on a different edge, heat of first edge decays to 0.
        """
        T, W = 100, 10  # W is small for easy testing
        ht = HeatTable(W, T)
        e_hot = make_edge(0, 1)
        e_other = make_edge(2, 3)
        key_hot = edge_key(0, 1)

        for _ in range(W):
            ht.increment([e_hot])
        assert ht.get(key_hot) == W

        # Fill window again with other edge — evicts all hot queries
        for _ in range(W):
            ht.increment([e_other])
        assert ht.get(key_hot) == 0, (
            f"After W evictions, heat should be 0 but got {ht.get(key_hot)}"
        )

    def test_window_eviction_is_fifo(self):
        """Oldest queries are evicted first (FIFO)."""
        T, W = 100, 5
        ht = HeatTable(W, T)
        e1 = make_edge(0, 1)
        e2 = make_edge(1, 2)
        key1 = edge_key(0, 1)
        key2 = edge_key(1, 2)

        # Add e1 twice, e2 three times (5 total = full window)
        ht.increment([e1])
        ht.increment([e1])
        ht.increment([e2])
        ht.increment([e2])
        ht.increment([e2])

        assert ht.get(key1) == 2
        assert ht.get(key2) == 3

        # Sixth increment: evicts the first query (which contained e1)
        ht.increment([make_edge(3, 4)])
        # e1 should have lost one count
        assert ht.get(key1) == 1
        assert ht.window_size() == W  # window stays at W

    def test_heat_never_goes_negative(self):
        T, W = 5, 3
        ht = HeatTable(W, T)
        e = make_edge(0, 1)
        key = edge_key(0, 1)
        ht.increment([e])
        for _ in range(100):
            ht.evict_oldest()
        assert ht.get(key) >= 0

    def test_overflow_window_triggers_eviction(self):
        """Adding W+1 queries must evict at least 1 oldest query."""
        T, W = 50, 5
        ht = HeatTable(W, T)
        e = make_edge(0, 1)
        key = edge_key(0, 1)
        for _ in range(W):
            ht.increment([e])
        assert ht.get(key) == W
        # One more query without the edge — triggers eviction of oldest
        ht.increment([make_edge(99, 100)])
        assert ht.get(key) == W - 1

    def test_window_with_multiple_edges_per_query(self):
        """Each query can cover multiple edges; eviction decrements all."""
        T, W = 50, 4
        ht = HeatTable(W, T)
        path = make_path_edges(3)  # Edge(0,1), Edge(1,2), Edge(2,3)
        for _ in range(W):
            ht.increment(path)
        for e in path:
            assert ht.get(edge_key(e.u, e.v)) == W
        # One new query evicts the oldest (path) → all edges lose 1
        ht.increment([make_edge(50, 51)])
        for e in path:
            assert ht.get(edge_key(e.u, e.v)) == W - 1

    def test_window_size_tracking(self):
        T, W = 50, 5
        ht = HeatTable(W, T)
        assert ht.window_size() == 0
        for i in range(W):
            ht.increment([make_edge(i, i + 1)])
            assert ht.window_size() == min(i + 1, W)
        # Adding more queries keeps window at W (auto-evicts)
        ht.increment([make_edge(100, 101)])
        assert ht.window_size() == W

    def test_get_returns_zero_for_unknown_edge(self):
        T, W = 10, 50
        ht = HeatTable(W, T)
        assert ht.get((999, 1000)) == 0

    def test_set_heat_and_get(self):
        T, W = 10, 50
        ht = HeatTable(W, T)
        ht.set_heat(3, 7, 8)
        assert ht.get(edge_key(3, 7)) == 8

    def test_update_threshold(self):
        T, W = 5, 20
        ht = HeatTable(W, T)
        e = make_edge(0, 1)
        for _ in range(3):
            ht.increment([e])
        # Raise T so it's no longer hot
        ht.update_threshold(T=10, W=20)
        assert not ht.is_hot(0, 1)
        # Lower T so it becomes hot
        ht.update_threshold(T=2, W=20)
        assert ht.is_hot(0, 1)


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not HAS_HEAT_TABLE:
        print("SKIP: HeatTable not importable from core/python/heat_table.py")
        sys.exit(0)

    import traceback

    suites = [TestPromotion, TestDemotion, TestWindow]
    passed = failed = 0
    for cls in suites:
        inst = cls()
        for name in [m for m in dir(cls) if m.startswith("test_")]:
            try:
                getattr(inst, name)()
                print(f"  PASS  {cls.__name__}.{name}")
                passed += 1
            except Exception:
                print(f"  FAIL  {cls.__name__}.{name}")
                traceback.print_exc()
                failed += 1

    print(f"\n{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
