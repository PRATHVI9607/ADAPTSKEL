"""
Adversarial workload generator for ADAPTSKEL benchmarks.

Generates a workload where queries are maximally spread across all source-target
pairs — the skeleton never crystallises because no path is queried twice.

This honestly demonstrates ADAPTSKEL's weakness: the algorithm is designed for
Zipf(α≥1) workloads. Under uniform-random queries the skeleton advantage
disappears and ADAPTSKEL degrades toward its O(log² n) worst-case cost.

See PRD §5.1 Generator 3 and §5.2 Figure 4 ("Adversarial Comparison").
"""
from __future__ import annotations

import random
from typing import NamedTuple

import networkx as nx


# ---------------------------------------------------------------------------
# Operation types (mirror zipf_workload for compatibility)
# ---------------------------------------------------------------------------

class InsertOp(NamedTuple):
    type: str
    u: int
    v: int
    w: float


class DeleteOp(NamedTuple):
    type: str
    u: int
    v: int


class QueryOp(NamedTuple):
    type: str
    s: int
    t: int


Operation = InsertOp | DeleteOp | QueryOp


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def generate_adversarial_workload(
    n: int,
    ops: int,
    insert_frac: float = 0.2,
    delete_frac: float = 0.1,
    query_frac: float = 0.7,
    seed: int = 42,
) -> tuple[nx.Graph, list[Operation]]:
    """
    Generate a uniform-random workload — the adversarial case for ADAPTSKEL.

    Every query picks a uniformly random (s, t) pair from all n*(n-1)/2
    possible pairs.  This prevents skeleton formation because no path is
    queried enough times to exceed the promotion threshold T.

    Parameters
    ----------
    n : int
        Number of vertices.
    ops : int
        Total number of operations.
    insert_frac, delete_frac, query_frac : float
        Operation mix fractions (normalised internally).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    graph : nx.Graph
        Initial random graph (gnm, ~3n edges).
    operations : list[Operation]
        Sequence of operations with uniformly random query targets.
    """
    rng = random.Random(seed)

    # Normalise fractions
    total = insert_frac + delete_frac + query_frac
    if total <= 0:
        raise ValueError("At least one fraction must be > 0")
    insert_frac /= total
    delete_frac /= total
    query_frac /= total

    # ------------------------------------------------------------------
    # Initial graph — sparse random (gnm)
    # ------------------------------------------------------------------
    m_edges = min(n * 3, max(n - 1, n * (n - 1) // 2))
    try:
        G = nx.gnm_random_graph(n, m_edges, seed=seed)
    except Exception:
        G = nx.path_graph(n)
    for u, v in G.edges():
        G[u][v]["weight"] = round(rng.uniform(1.0, 10.0), 2)

    nodes = list(range(n))
    current_edges: set[tuple[int, int]] = {
        (min(u, v), max(u, v)) for u, v in G.edges()
    }
    operations: list[Operation] = []

    for _ in range(ops):
        r = rng.random()

        if r < query_frac and n >= 2:
            # QUERY — completely uniform random: worst case for skeleton
            s = rng.randint(0, n - 1)
            t = rng.randint(0, n - 1)
            while t == s:
                t = rng.randint(0, n - 1)
            operations.append(QueryOp("QUERY", s, t))

        elif r < query_frac + insert_frac and n >= 2:
            # INSERT — random edge
            for _attempt in range(10):
                u = rng.randint(0, n - 1)
                v = rng.randint(0, n - 1)
                if u == v:
                    continue
                key = (min(u, v), max(u, v))
                if key not in current_edges:
                    w = round(rng.uniform(1.0, 10.0), 2)
                    operations.append(InsertOp("INSERT", u, v, w))
                    current_edges.add(key)
                    break

        elif current_edges:
            # DELETE — remove a random existing edge
            key = rng.choice(list(current_edges))
            operations.append(DeleteOp("DELETE", key[0], key[1]))
            current_edges.discard(key)

    return G, operations
