"""
Scaling benchmark generator for ADAPTSKEL.

Produces per-size workloads suitable for the "money plot":
  - X-axis: graph size n (log scale 100 → 100K)
  - Y-axis: average operation time (log scale)

Usage
-----
    from benchmarks.generators.scaling_benchmark import generate_scaling_benchmark
    workloads = generate_scaling_benchmark()
    for n, data in workloads.items():
        graph = data['graph']   # nx.Graph
        ops   = data['ops']     # list of Operation tuples
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx

from .zipf_workload import generate_zipf_workload, Operation

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def generate_scaling_benchmark(
    sizes: list[int] | None = None,
    ops_per_size: int = 1000,
    alpha: float = 1.2,
    insert_frac: float = 0.2,
    delete_frac: float = 0.1,
    query_frac: float = 0.7,
    seed: int = 42,
) -> dict[int, dict]:
    """
    Generate Zipf workloads for multiple graph sizes.

    Parameters
    ----------
    sizes : list[int] | None
        Graph sizes (number of vertices) to benchmark.
        Default: [100, 500, 1000, 5000, 10000]
    ops_per_size : int
        Number of operations per size.
    alpha : float
        Zipf exponent for query distribution.
    insert_frac, delete_frac, query_frac : float
        Operation mix (will be normalised).
    seed : int
        Base random seed (each size gets seed + index for independence).

    Returns
    -------
    dict mapping n -> {'graph': nx.Graph, 'ops': list[Operation], 'n': int}
    """
    if sizes is None:
        sizes = [100, 500, 1000, 5000, 10000]

    results: dict[int, dict] = {}

    for idx, n in enumerate(sizes):
        # BA m parameter: each new node connects to ~3 existing (realistic)
        ba_m = max(1, min(3, n - 1))

        graph, ops = generate_zipf_workload(
            n=n,
            m=ba_m,
            num_queries=ops_per_size,
            alpha=alpha,
            insert_frac=insert_frac,
            delete_frac=delete_frac,
            query_frac=query_frac,
            seed=seed + idx,
        )

        results[n] = {
            "n": n,
            "graph": graph,
            "ops": ops,
            "edge_count": graph.number_of_edges(),
            "alpha": alpha,
            "ops_per_size": ops_per_size,
        }

    return results
