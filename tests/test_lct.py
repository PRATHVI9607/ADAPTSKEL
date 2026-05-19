"""
Unit tests for LinkCutTree (core/python/lct.py).

Covers:
  - link / connected
  - cut / disconnected
  - path_query on chains and trees
  - find_root after various operations
  - path_nodes returns correct ordered list
  - edge weight retrieval
  - has_edge / all_edges
  - stale / dist label helpers
"""
from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core', 'python'))

from lct import LinkCutTree  # type: ignore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_lct(*nodes: int) -> LinkCutTree:
    """Create an LCT and register the given node IDs."""
    lct = LinkCutTree()
    for v in nodes:
        lct.add_node(v)
    return lct


# ---------------------------------------------------------------------------
# test_link_connected
# ---------------------------------------------------------------------------

class TestLinkConnected:
    def test_isolated_nodes_not_connected(self):
        lct = make_lct(0, 1, 2)
        assert not lct.connected(0, 1)
        assert not lct.connected(1, 2)
        assert not lct.connected(0, 2)

    def test_link_two_nodes(self):
        lct = make_lct(0, 1)
        lct.link(0, 1, 3.0)
        assert lct.connected(0, 1)

    def test_self_connected(self):
        lct = make_lct(5)
        assert lct.connected(5, 5)

    def test_link_chain_all_connected(self):
        lct = make_lct(0, 1, 2, 3)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 2.0)
        lct.link(2, 3, 3.0)
        assert lct.connected(0, 3)
        assert lct.connected(1, 3)
        assert lct.connected(0, 2)

    def test_two_separate_components(self):
        lct = make_lct(0, 1, 2, 3)
        lct.link(0, 1, 1.0)
        lct.link(2, 3, 1.0)
        assert lct.connected(0, 1)
        assert lct.connected(2, 3)
        assert not lct.connected(0, 2)
        assert not lct.connected(1, 3)

    def test_merge_components_via_link(self):
        lct = make_lct(0, 1, 2, 3)
        lct.link(0, 1, 1.0)
        lct.link(2, 3, 1.0)
        assert not lct.connected(0, 2)
        lct.link(1, 2, 5.0)
        assert lct.connected(0, 3)


# ---------------------------------------------------------------------------
# test_cut_disconnected
# ---------------------------------------------------------------------------

class TestCutDisconnected:
    def test_cut_single_edge(self):
        lct = make_lct(0, 1)
        lct.link(0, 1, 7.0)
        assert lct.connected(0, 1)
        lct.cut(0, 1)
        assert not lct.connected(0, 1)

    def test_cut_middle_of_chain(self):
        lct = make_lct(0, 1, 2)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 2.0)
        lct.cut(1, 2)
        assert lct.connected(0, 1)
        assert not lct.connected(0, 2)
        assert not lct.connected(1, 2)

    def test_cut_root_edge(self):
        lct = make_lct(0, 1, 2)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 2.0)
        lct.cut(0, 1)
        assert not lct.connected(0, 1)
        assert lct.connected(1, 2)

    def test_cut_and_relink(self):
        lct = make_lct(0, 1, 2)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 2.0)
        lct.cut(1, 2)
        assert not lct.connected(1, 2)
        lct.link(1, 2, 99.0)
        assert lct.connected(0, 2)

    def test_has_edge_after_cut(self):
        lct = make_lct(10, 20)
        lct.link(10, 20, 5.0)
        assert lct.has_edge(10, 20)
        lct.cut(10, 20)
        assert not lct.has_edge(10, 20)


# ---------------------------------------------------------------------------
# test_path_query
# ---------------------------------------------------------------------------

class TestPathQuery:
    def test_single_edge_path(self):
        lct = make_lct(0, 1)
        lct.link(0, 1, 4.5)
        result = lct.path_query(0, 1)
        assert abs(result - 4.5) < 1e-9

    def test_chain_a_b_c(self):
        """A-B-C chain, path A→C should be w(A,B)+w(B,C)."""
        lct = make_lct(0, 1, 2)
        lct.link(0, 1, 3.0)
        lct.link(1, 2, 5.0)
        result = lct.path_query(0, 2)
        assert abs(result - 8.0) < 1e-9

    def test_longer_chain(self):
        """0-1-2-3-4 chain."""
        lct = make_lct(0, 1, 2, 3, 4)
        weights = [1.0, 2.5, 0.5, 3.0]
        for i in range(4):
            lct.link(i, i + 1, weights[i])
        result = lct.path_query(0, 4)
        assert abs(result - sum(weights)) < 1e-9

    def test_tree_path_not_direct(self):
        """
        Tree: 0-1, 1-2, 1-3.
        Path 2→3 goes through 1: w(2,1)+w(1,3).
        """
        lct = make_lct(0, 1, 2, 3)
        lct.link(0, 1, 10.0)
        lct.link(1, 2, 2.0)
        lct.link(1, 3, 4.0)
        result = lct.path_query(2, 3)
        assert abs(result - 6.0) < 1e-9

    def test_path_query_symmetric(self):
        lct = make_lct(5, 6)
        lct.link(5, 6, 7.3)
        assert abs(lct.path_query(5, 6) - lct.path_query(6, 5)) < 1e-9

    def test_path_query_after_cut_relink(self):
        lct = make_lct(0, 1)
        lct.link(0, 1, 3.0)
        lct.cut(0, 1)
        lct.link(0, 1, 9.9)
        assert abs(lct.path_query(0, 1) - 9.9) < 1e-9


# ---------------------------------------------------------------------------
# test_find_root
# ---------------------------------------------------------------------------

class TestFindRoot:
    def test_isolated_node_is_own_root(self):
        lct = make_lct(42)
        assert lct.find_root(42) == 42

    def test_root_after_single_link(self):
        """After link(0,1), root of one component is consistent."""
        lct = make_lct(0, 1)
        lct.link(0, 1, 1.0)
        r0 = lct.find_root(0)
        r1 = lct.find_root(1)
        # Both nodes must be in the same tree → same root
        assert r0 == r1

    def test_root_is_stable_after_multiple_links(self):
        lct = make_lct(0, 1, 2, 3)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 1.0)
        lct.link(2, 3, 1.0)
        r0 = lct.find_root(0)
        r3 = lct.find_root(3)
        assert r0 == r3

    def test_root_changes_after_cut(self):
        """After cutting A-B, A and B are in separate trees."""
        lct = make_lct(0, 1, 2)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 1.0)
        lct.cut(0, 1)
        # 0 is isolated; 1 and 2 share a root
        r1 = lct.find_root(1)
        r2 = lct.find_root(2)
        assert r1 == r2
        # 0's root is itself (isolated)
        assert lct.find_root(0) == 0

    def test_root_separate_components(self):
        lct = make_lct(10, 20, 30, 40)
        lct.link(10, 20, 1.0)
        lct.link(30, 40, 1.0)
        r_a = lct.find_root(10)
        r_b = lct.find_root(30)
        # Different components — roots must differ
        assert r_a != r_b

    def test_make_root_via_access_pattern(self):
        """find_root twice on the same node returns the same value."""
        lct = make_lct(0, 1, 2)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 1.0)
        first = lct.find_root(2)
        second = lct.find_root(2)
        assert first == second


# ---------------------------------------------------------------------------
# test_path_nodes
# ---------------------------------------------------------------------------

class TestPathNodes:
    def test_single_edge_path_nodes(self):
        lct = make_lct(0, 1)
        lct.link(0, 1, 5.0)
        nodes = lct.path_nodes(0, 1)
        assert sorted(nodes) == [0, 1]

    def test_chain_path_nodes(self):
        lct = make_lct(0, 1, 2)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 2.0)
        nodes = lct.path_nodes(0, 2)
        assert sorted(nodes) == [0, 1, 2]

    def test_path_nodes_order(self):
        """path_nodes should return nodes in path order from u to v."""
        lct = make_lct(0, 1, 2, 3)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 2.0)
        lct.link(2, 3, 3.0)
        nodes = lct.path_nodes(0, 3)
        # Must include all four
        assert sorted(nodes) == [0, 1, 2, 3]
        # Must be a valid ordering: each consecutive pair is an edge
        for i in range(len(nodes) - 1):
            assert lct.has_edge(nodes[i], nodes[i + 1]), (
                f"path_nodes not in edge order: {nodes}"
            )

    def test_path_nodes_self(self):
        lct = make_lct(7)
        nodes = lct.path_nodes(7, 7)
        assert nodes == [7]

    def test_path_nodes_tree_branch(self):
        """Tree: 0-1-2, 1-3. Path 0→3 must go through 1."""
        lct = make_lct(0, 1, 2, 3)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 2.0)
        lct.link(1, 3, 4.0)
        nodes = lct.path_nodes(0, 3)
        assert sorted(nodes) == [0, 1, 3]

    def test_path_nodes_length_matches_path_query(self):
        """For a chain, path_nodes length == path_query edge count + 1."""
        lct = make_lct(0, 1, 2, 3, 4)
        weights = [1.0, 2.0, 3.0, 4.0]
        for i in range(4):
            lct.link(i, i + 1, weights[i])
        nodes = lct.path_nodes(0, 4)
        assert len(nodes) == 5  # 5 nodes on path 0-1-2-3-4

    def test_path_nodes_symmetric(self):
        lct = make_lct(0, 1, 2)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 2.0)
        fwd = lct.path_nodes(0, 2)
        bwd = lct.path_nodes(2, 0)
        assert sorted(fwd) == sorted(bwd)


# ---------------------------------------------------------------------------
# Additional: has_edge / all_edges / dist labels
# ---------------------------------------------------------------------------

class TestAuxiliary:
    def test_has_edge_before_and_after_link(self):
        lct = make_lct(0, 1)
        assert not lct.has_edge(0, 1)
        lct.link(0, 1, 1.0)
        assert lct.has_edge(0, 1)
        assert lct.has_edge(1, 0)  # symmetric

    def test_all_edges_count(self):
        lct = make_lct(0, 1, 2, 3)
        lct.link(0, 1, 1.0)
        lct.link(1, 2, 2.0)
        lct.link(2, 3, 3.0)
        assert len(lct.all_edges()) == 3
        lct.cut(1, 2)
        assert len(lct.all_edges()) == 2

    def test_dist_labels(self):
        lct = make_lct(0, 1, 2)
        assert lct.get_dist(0) == float("inf")
        lct.set_dist(0, 0.0)
        lct.set_dist(1, 5.0)
        assert lct.get_dist(0) == 0.0
        assert lct.get_dist(1) == 5.0

    def test_stale_marks(self):
        lct = make_lct(0, 1)
        assert not lct.is_stale(0)
        lct.mark_stale(0)
        assert lct.is_stale(0)
        lct.mark_fresh(0)
        assert not lct.is_stale(0)

    def test_heat_labels(self):
        lct = make_lct(0, 1)
        assert lct.get_heat(0) == 0
        lct.set_heat(0, 42)
        assert lct.get_heat(0) == 42

    def test_get_edge_weight(self):
        lct = make_lct(0, 1)
        lct.link(0, 1, 3.14)
        w = lct.get_edge_weight(0, 1)
        assert abs(w - 3.14) < 1e-9

    def test_contains_operator(self):
        lct = make_lct(5, 10)
        assert 5 in lct
        assert 10 in lct
        assert 99 not in lct


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    suites = [
        TestLinkConnected, TestCutDisconnected, TestPathQuery,
        TestFindRoot, TestPathNodes, TestAuxiliary,
    ]
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
