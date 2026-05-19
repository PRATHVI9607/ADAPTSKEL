"""
Road network simulator for ADAPTSKEL benchmarks.

Creates a grid graph (approximating a city road layout) with:
  - Grid edges: travel time ~ Uniform(1, 5) minutes
  - Random shortcuts (flyovers / ring roads): travel time ~ Uniform(0.5, 2) min
  - Periodic congestion events (edge weight increases)
  - Road closures (DELETE) and openings (INSERT)

Road networks have large diameter O(√n) — a challenging case for ADAPTSKEL
because shortest paths are longer and span more edges.

Usage
-----
    from benchmarks.generators.road_network import generate_road_network
    G = generate_road_network(grid_size=20)

    # Generate a dynamic workload on top:
    from benchmarks.generators.road_network import generate_road_workload
    graph, ops = generate_road_workload(grid_size=20, num_ops=2000)
"""
from __future__ import annotations

import random
from typing import NamedTuple

import networkx as nx


# ---------------------------------------------------------------------------
# Operation types
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
# Graph generation
# ---------------------------------------------------------------------------

def generate_road_network(
    grid_size: int = 20,
    shortcut_prob: float = 0.1,
    seed: int = 42,
) -> nx.Graph:
    """
    Generate a grid graph with random shortcuts — simulates a road network.

    Parameters
    ----------
    grid_size : int
        Side length of the grid.  Total nodes = grid_size².
    shortcut_prob : float
        Probability of adding a shortcut between two non-adjacent nodes.
        Shortcuts model flyovers, ring roads, and highways.
    seed : int
        Random seed.

    Returns
    -------
    nx.Graph with integer node labels (0 … grid_size²-1) and 'weight' edges.
    """
    rng = random.Random(seed)

    # ------------------------------------------------------------------
    # 1. Start with 2D grid
    # ------------------------------------------------------------------
    G2d = nx.grid_2d_graph(grid_size, grid_size)
    G = nx.convert_node_labels_to_integers(G2d)

    # Assign random grid weights (travel time: 1–5 min)
    for u, v in G.edges():
        G[u][v]["weight"] = round(rng.uniform(1.0, 5.0), 2)

    # ------------------------------------------------------------------
    # 2. Add random shortcut edges (flyovers / ring roads)
    # ------------------------------------------------------------------
    nodes = list(G.nodes())
    n = len(nodes)
    num_shortcuts = int(n * shortcut_prob)

    for _ in range(num_shortcuts * 5):  # attempt more, skip duplicates
        u = rng.choice(nodes)
        v = rng.choice(nodes)
        if u != v and not G.has_edge(u, v):
            # Shortcuts are faster than grid roads
            G.add_edge(u, v, weight=round(rng.uniform(0.5, 2.0), 2))
            num_shortcuts -= 1
            if num_shortcuts <= 0:
                break

    return G


# ---------------------------------------------------------------------------
# Dynamic workload on road network
# ---------------------------------------------------------------------------

def generate_road_workload(
    grid_size: int = 20,
    shortcut_prob: float = 0.1,
    num_ops: int = 2000,
    closure_prob: float = 0.001,
    congestion_prob: float = 0.05,
    seed: int = 42,
) -> tuple[nx.Graph, list[Operation]]:
    """
    Generate a road network and a realistic dynamic workload.

    The workload models:
    - Traffic queries (commuters travelling between fixed origin/destination pairs)
    - Road closures (accidents, construction): DELETE edges
    - New road openings: INSERT edges
    - Congestion events: simulated as DELETE + INSERT with higher weight

    Parameters
    ----------
    grid_size : int
        Grid side length.
    shortcut_prob : float
        Shortcut probability for initial graph.
    num_ops : int
        Number of operations to generate.
    closure_prob : float
        Per-timestep probability that a road is closed.
    congestion_prob : float
        Per-timestep probability that a road becomes congested (weight up).
    seed : int
        Random seed.

    Returns
    -------
    (graph, ops) where graph is the initial network and ops is the sequence.
    """
    rng = random.Random(seed)
    G = generate_road_network(grid_size=grid_size, shortcut_prob=shortcut_prob, seed=seed)
    nodes = list(G.nodes())

    # Pick "commuter" origin-destination pairs (fixed, like real commuters)
    n = len(nodes)
    num_od_pairs = max(4, n // 10)
    od_pairs = [(rng.choice(nodes), rng.choice(nodes)) for _ in range(num_od_pairs)]
    od_pairs = [(s, t) for s, t in od_pairs if s != t]
    if not od_pairs:
        od_pairs = [(nodes[0], nodes[-1])]

    current_edges: set[tuple[int, int]] = {
        (min(u, v), max(u, v)) for u, v in G.edges()
    }
    current_weights: dict[tuple[int, int], float] = {
        (min(u, v), max(u, v)): data["weight"]
        for u, v, data in G.edges(data=True)
    }

    ops: list[Operation] = []

    for step in range(num_ops):
        r = rng.random()

        if r < 0.60 and od_pairs:
            # QUERY: commuter travels between OD pair
            s, t = rng.choice(od_pairs)
            ops.append(QueryOp("QUERY", s, t))

        elif r < 0.65 and current_edges and rng.random() < closure_prob * 100:
            # DELETE: road closure (rare)
            key = rng.choice(list(current_edges))
            ops.append(DeleteOp("DELETE", key[0], key[1]))
            current_edges.discard(key)
            current_weights.pop(key, None)

        elif r < 0.75 and current_edges and rng.random() < congestion_prob * 10:
            # CONGESTION: delete + reinsert with higher weight
            key = rng.choice(list(current_edges))
            u, v = key
            old_w = current_weights.get(key, 3.0)
            new_w = round(min(old_w * rng.uniform(1.5, 3.0), 30.0), 2)
            ops.append(DeleteOp("DELETE", u, v))
            ops.append(InsertOp("INSERT", u, v, new_w))
            current_weights[key] = new_w

        elif r < 0.80 and len(nodes) >= 2:
            # INSERT: new road opening (rare)
            for _attempt in range(5):
                u = rng.choice(nodes)
                v = rng.choice(nodes)
                if u == v:
                    continue
                key = (min(u, v), max(u, v))
                if key not in current_edges:
                    w = round(rng.uniform(0.5, 5.0), 2)
                    ops.append(InsertOp("INSERT", u, v, w))
                    current_edges.add(key)
                    current_weights[key] = w
                    break

        else:
            # QUERY: random background traffic
            if len(nodes) >= 2:
                s = rng.choice(nodes)
                t = rng.choice(nodes)
                if s != t:
                    ops.append(QueryOp("QUERY", s, t))

    return G, ops
