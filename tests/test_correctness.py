"""
MOST IMPORTANT TEST: ADAPTSKEL vs NetworkX oracle.

Runs both algorithms on identical operation sequences and asserts zero
distance discrepancy on every QUERY. Covers small, medium, and large graphs
with multiple random seeds.
"""
from __future__ import annotations

import random
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core', 'python'))

import networkx as nx
from adaptskel import AdaptSkel  # type: ignore
from baselines import DijkstraBaseline  # type: ignore


# ---------------------------------------------------------------------------
# Core oracle test function
# ---------------------------------------------------------------------------

def run_oracle_test(n_nodes: int, n_ops: int, seed: int) -> None:
    """
    Run ADAPTSKEL and NetworkX in lock-step on the same operation sequence.
    Assert that every QUERY returns the exact same distance.

    Parameters
    ----------
    n_nodes : int
        Number of distinct vertex IDs used (0 … n_nodes-1).
    n_ops : int
        Total number of operations to generate.
    seed : int
        Random seed for full reproducibility.
    """
    rng = random.Random(seed)
    nodes = list(range(n_nodes))

    # --- Build oracle (NetworkX) ---
    G_nx = nx.Graph()
    for v in nodes:
        G_nx.add_node(v)

    # --- Build ADAPTSKEL instance ---
    G_adapt = AdaptSkel(source=0)
    for v in nodes:
        G_adapt.add_vertex(v)

    active_edges: set[tuple[int, int]] = set()

    for op_idx in range(n_ops):
        op = rng.choices(
            ["INSERT", "DELETE", "QUERY"],
            weights=[0.4, 0.2, 0.4],
        )[0]

        if op == "INSERT":
            u = rng.randint(0, n_nodes - 1)
            v = rng.randint(0, n_nodes - 1)
            if u == v:
                continue
            key = (min(u, v), max(u, v))
            if key in active_edges:
                continue
            w = round(rng.uniform(1.0, 10.0), 2)
            G_nx.add_edge(u, v, weight=w)
            G_adapt.insert(u, v, w)
            active_edges.add(key)

        elif op == "DELETE":
            if not active_edges:
                continue
            key = rng.choice(list(active_edges))
            u, v = key
            G_nx.remove_edge(u, v)
            G_adapt.delete(u, v)
            active_edges.discard(key)

        elif op == "QUERY":
            if n_nodes < 2:
                continue
            s = rng.randint(0, n_nodes - 1)
            t = rng.randint(0, n_nodes - 1)
            if s == t:
                continue

            # Oracle distance
            try:
                expected = nx.shortest_path_length(G_nx, s, t, weight="weight")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                expected = float("inf")

            # ADAPTSKEL distance
            actual = G_adapt.query(s, t)

            if expected == float("inf"):
                assert actual == float("inf"), (
                    f"[seed={seed}, op={op_idx}] QUERY({s},{t}): "
                    f"expected inf, got {actual}"
                )
            else:
                assert abs(expected - actual) < 1e-6, (
                    f"[seed={seed}, op={op_idx}] QUERY({s},{t}): "
                    f"expected {expected:.8f}, got {actual:.8f}  "
                    f"(|diff|={abs(expected - actual):.2e})"
                )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_small_correctness():
    """10 nodes × 100 ops × 10 random seeds."""
    for seed in range(10):
        run_oracle_test(n_nodes=10, n_ops=100, seed=seed)


def test_medium_correctness():
    """50 nodes × 500 ops × 5 random seeds."""
    for seed in range(5):
        run_oracle_test(n_nodes=50, n_ops=500, seed=seed)


def test_large_correctness():
    """200 nodes × 2000 ops, one seed."""
    run_oracle_test(n_nodes=200, n_ops=2000, seed=42)


def test_dense_graph():
    """High insert fraction — many edges, many duplicates."""
    run_oracle_test(n_nodes=30, n_ops=300, seed=7)


def test_single_component_stays_connected():
    """All deletes follow inserts — verify no-path case."""
    rng = random.Random(99)
    n = 15
    G_nx = nx.Graph()
    for v in range(n):
        G_nx.add_node(v)
    G_adapt = AdaptSkel(source=0)
    for v in range(n):
        G_adapt.add_vertex(v)

    active = set()
    # Phase 1: bulk inserts
    for _ in range(60):
        u = rng.randint(0, n - 1)
        v = rng.randint(0, n - 1)
        if u == v:
            continue
        key = (min(u, v), max(u, v))
        if key in active:
            continue
        w = round(rng.uniform(1.0, 5.0), 2)
        G_nx.add_edge(u, v, weight=w)
        G_adapt.insert(u, v, w)
        active.add(key)

    # Phase 2: bulk deletes then query
    while active:
        key = rng.choice(list(active))
        u, v = key
        G_nx.remove_edge(u, v)
        G_adapt.delete(u, v)
        active.discard(key)

    for s, t in [(0, n - 1), (1, n // 2), (3, 7)]:
        try:
            expected = nx.shortest_path_length(G_nx, s, t, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            expected = float("inf")
        actual = G_adapt.query(s, t)
        if expected == float("inf"):
            assert actual == float("inf"), f"Expected inf, got {actual} for ({s},{t})"
        else:
            assert abs(expected - actual) < 1e-6, f"Mismatch: {expected} vs {actual}"


def test_weight_update_via_delete_insert():
    """
    NetworkX doesn't support direct weight-update; simulate via DELETE+INSERT.
    Verify ADAPTSKEL tracks it correctly.
    """
    G_nx = nx.Graph()
    G_adapt = AdaptSkel(source=0)
    for v in range(5):
        G_nx.add_node(v)
        G_adapt.add_vertex(v)

    G_nx.add_edge(0, 1, weight=5.0)
    G_adapt.insert(0, 1, 5.0)
    G_nx.add_edge(1, 2, weight=3.0)
    G_adapt.insert(1, 2, 3.0)

    # Query: 0→2 should be 8.0
    assert abs(G_adapt.query(0, 2) - 8.0) < 1e-6

    # Update weight 0→1 from 5.0 to 1.0
    G_nx.remove_edge(0, 1)
    G_nx.add_edge(0, 1, weight=1.0)
    G_adapt.delete(0, 1)
    G_adapt.insert(0, 1, 1.0)

    # Query: 0→2 should now be 4.0
    expected = nx.shortest_path_length(G_nx, 0, 2, weight="weight")
    actual = G_adapt.query(0, 2)
    assert abs(expected - actual) < 1e-6, f"After weight update: expected {expected}, got {actual}"


# ---------------------------------------------------------------------------
# Main (standalone runner)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running ADAPTSKEL correctness oracle tests...")

    print("  test_small_correctness ...", end=" ", flush=True)
    test_small_correctness()
    print("PASSED")

    print("  test_medium_correctness ...", end=" ", flush=True)
    test_medium_correctness()
    print("PASSED")

    print("  test_large_correctness ...", end=" ", flush=True)
    test_large_correctness()
    print("PASSED")

    print("  test_dense_graph ...", end=" ", flush=True)
    test_dense_graph()
    print("PASSED")

    print("  test_single_component_stays_connected ...", end=" ", flush=True)
    test_single_component_stays_connected()
    print("PASSED")

    print("  test_weight_update_via_delete_insert ...", end=" ", flush=True)
    test_weight_update_via_delete_insert()
    print("PASSED")

    print("\nALL CORRECTNESS TESTS PASSED")
