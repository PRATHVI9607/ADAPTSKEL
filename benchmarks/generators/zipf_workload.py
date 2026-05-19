"""
Zipf workload generator for ADAPTSKEL benchmarks.

Generates a Barabasi-Albert graph and a query/update workload where queries
follow a Zipf distribution over "popular" source-target pairs (hub nodes).

This models realistic workloads where a small fraction of paths carry the
majority of queries (road networks α≈1.3, social graphs α≈1.7, routing α≈1.2).
"""
from __future__ import annotations

import random
from math import ceil, log2
from typing import NamedTuple

import networkx as nx


# ---------------------------------------------------------------------------
# Operation types
# ---------------------------------------------------------------------------

class InsertOp(NamedTuple):
    type: str          # "INSERT"
    u: int
    v: int
    w: float


class DeleteOp(NamedTuple):
    type: str          # "DELETE"
    u: int
    v: int


class QueryOp(NamedTuple):
    type: str          # "QUERY"
    s: int
    t: int


Operation = InsertOp | DeleteOp | QueryOp


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def generate_zipf_workload(
    n: int,
    m: int,
    num_queries: int,
    alpha: float = 1.2,
    insert_frac: float = 0.2,
    delete_frac: float = 0.1,
    query_frac: float = 0.7,
    seed: int = 42,
) -> tuple[nx.Graph, list[Operation]]:
    """
    Generate a Barabasi-Albert graph and a Zipf-distributed workload.

    Parameters
    ----------
    n : int
        Number of vertices.
    m : int
        Number of edges per new node in the BA model (connectivity parameter).
        If m >= n, falls back to a random graph with ~n*3 edges.
    num_queries : int
        Total number of operations to generate.
    alpha : float
        Zipf exponent.  Higher α → more concentrated query distribution.
        Typical values: road=1.3, social=1.7, routing=1.2.
    insert_frac : float
        Fraction of operations that are insertions.
    delete_frac : float
        Fraction of operations that are deletions.
    query_frac : float
        Fraction of operations that are queries.
        insert_frac + delete_frac + query_frac should sum to 1.0.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    graph : nx.Graph
        Initial graph (Barabasi-Albert).  Edge weights are random in [1, 10].
    ops : list[Operation]
        Sequence of operations to apply to the graph.
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
    # 1. Generate initial graph
    # ------------------------------------------------------------------
    ba_m = max(1, min(m, n - 1))
    try:
        G = nx.barabasi_albert_graph(n, ba_m, seed=seed)
    except Exception:
        # Fallback for very small n
        G = nx.gnm_random_graph(n, min(n * 3, n * (n - 1) // 2), seed=seed)

    for u, v in G.edges():
        G[u][v]["weight"] = round(rng.uniform(1.0, 10.0), 2)

    # ------------------------------------------------------------------
    # 2. Identify "hub" nodes (high-degree nodes = popular in BA graphs)
    # ------------------------------------------------------------------
    num_hubs = max(2, ceil(log2(max(n, 2))))
    sorted_nodes = sorted(G.nodes(), key=lambda v: G.degree(v), reverse=True)
    hubs = sorted_nodes[:num_hubs]

    # All hub-to-hub pairs as popular query targets
    popular_pairs = [(s, t) for s in hubs for t in hubs if s != t]
    if not popular_pairs:
        # Fallback: use all node pairs up to some limit
        nodes = list(G.nodes())
        popular_pairs = [(nodes[i], nodes[j])
                         for i in range(len(nodes))
                         for j in range(i + 1, min(i + 6, len(nodes)))]

    # ------------------------------------------------------------------
    # 3. Build Zipf probability distribution over popular_pairs
    # ------------------------------------------------------------------
    zipf_weights = [1.0 / ((k + 1) ** alpha) for k in range(len(popular_pairs))]
    w_total = sum(zipf_weights)
    zipf_weights = [w / w_total for w in zipf_weights]

    # ------------------------------------------------------------------
    # 4. Generate operation sequence
    # ------------------------------------------------------------------
    current_edges: set[tuple[int, int]] = {
        (min(u, v), max(u, v)) for u, v in G.edges()
    }
    all_nodes = list(G.nodes())
    ops: list[Operation] = []

    for _ in range(num_queries):
        r = rng.random()

        if r < query_frac and popular_pairs:
            # QUERY — Zipf distribution over hub pairs
            pair = rng.choices(popular_pairs, weights=zipf_weights, k=1)[0]
            ops.append(QueryOp("QUERY", pair[0], pair[1]))

        elif r < query_frac + insert_frac and len(all_nodes) >= 2:
            # INSERT — random new edge (up to 10 attempts to find a fresh one)
            for _attempt in range(10):
                u = rng.choice(all_nodes)
                v = rng.choice(all_nodes)
                if u == v:
                    continue
                key = (min(u, v), max(u, v))
                if key not in current_edges:
                    w = round(rng.uniform(1.0, 10.0), 2)
                    ops.append(InsertOp("INSERT", u, v, w))
                    current_edges.add(key)
                    break

        elif current_edges:
            # DELETE — remove a random existing edge
            key = rng.choice(list(current_edges))
            ops.append(DeleteOp("DELETE", key[0], key[1]))
            current_edges.discard(key)

    return G, ops
