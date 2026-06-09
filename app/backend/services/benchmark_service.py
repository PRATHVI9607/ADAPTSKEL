"""
BenchmarkService — runs AdaptSkel vs Dijkstra head-to-head benchmarks.

Benchmarks run in background daemon threads to avoid blocking FastAPI.
Results are stored in memory keyed by benchmark_id.
"""
from __future__ import annotations

import os
import random
import sys
import threading
import time
from math import ceil, log2
from statistics import mean, median, stdev
from typing import Any

import networkx as nx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'core', 'python'))

# ---------------------------------------------------------------------------
# Dijkstra Baseline
# ---------------------------------------------------------------------------

class DijkstraBaseline:
    """Rerun NetworkX Dijkstra for every query — O(E log V) baseline."""

    def __init__(self) -> None:
        self._g: nx.Graph = nx.Graph()

    def insert(self, u: int, v: int, w: float) -> None:
        self._g.add_edge(u, v, weight=w)

    def delete(self, u: int, v: int) -> None:
        if self._g.has_edge(u, v):
            self._g.remove_edge(u, v)

    def query(self, s: int, t: int) -> float:
        try:
            return nx.shortest_path_length(self._g, s, t, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return float("inf")


# ---------------------------------------------------------------------------
# BenchmarkService
# ---------------------------------------------------------------------------

class BenchmarkService:
    """Manages benchmark runs, stores results and status."""

    def __init__(self) -> None:
        self._results: dict[str, dict] = {}
        self._status: dict[str, dict] = {}
        self._threads: dict[str, threading.Thread] = {}

    # ------------------------------------------------------------------
    def start_benchmark(self, benchmark_id: str, config: dict) -> None:
        """Start benchmark in a background daemon thread."""
        self._status[benchmark_id] = {"status": "running", "progress": 0.0}
        t = threading.Thread(
            target=self._run,
            args=(benchmark_id, config),
            daemon=True,
            name=f"benchmark-{benchmark_id}",
        )
        self._threads[benchmark_id] = t
        t.start()

    def get_status(self, benchmark_id: str) -> dict:
        return self._status.get(benchmark_id, {"status": "not_found", "progress": 0.0})

    def get_results(self, benchmark_id: str) -> dict:
        return self._results.get(benchmark_id, {})

    # ------------------------------------------------------------------
    def _run(self, benchmark_id: str, config: dict) -> None:
        """Core benchmark logic — generates workload, times both algorithms."""
        try:
            n = config.get("node_count", 100)
            total_ops = config.get("operations", 1000)
            graph_type = config.get("graph_type", "random")
            qmix = config.get("query_mix", {"insert": 0.2, "delete": 0.1, "query": 0.7})
            alpha = config.get("zipf_alpha", 1.2)

            insert_frac = qmix.get("insert", 0.2)
            delete_frac = qmix.get("delete", 0.1)
            query_frac = qmix.get("query", 0.7)

            # 1. Generate initial graph
            G_init = _generate_initial_graph(graph_type, n)

            # 2. Generate operations sequence
            ops = _generate_ops(G_init, total_ops, alpha, insert_frac, delete_frac, query_frac)

            def _update_progress(done: int, phase: str) -> None:
                self._status[benchmark_id] = {
                    "status": "running",
                    "progress": round(done / (total_ops * 2), 4),
                    "phase": phase,
                }

            # 3. Run AdaptSkel
            adapt_insert_us, adapt_delete_us, adapt_query_us, hot_ratio, f1_count = \
                _run_adaptskel_benchmark(G_init, ops, benchmark_id, self._status, total_ops)
            _update_progress(total_ops, "dijkstra")

            # 4. Run Dijkstra baseline
            dijk_insert_us, dijk_delete_us, dijk_query_us = \
                _run_dijkstra_benchmark(G_init, ops, benchmark_id, self._status, total_ops)

            # 5. Compute speedup
            adapt_avg = mean(adapt_query_us) if adapt_query_us else 0.001
            dijk_avg = mean(dijk_query_us) if dijk_query_us else 0.001
            speedup = round(dijk_avg / adapt_avg, 2) if adapt_avg > 0 else 1.0

            # 6. Generate scaling_data (sizes around n)
            scaling_data = _generate_scaling_data(n, graph_type, alpha, insert_frac, delete_frac, query_frac)

            self._results[benchmark_id] = {
                "adaptskel": {
                    "avg_insert_us": round(mean(adapt_insert_us), 2) if adapt_insert_us else 0.0,
                    "avg_delete_us": round(mean(adapt_delete_us), 2) if adapt_delete_us else 0.0,
                    "avg_query_us": round(adapt_avg, 2),
                    "speedup": speedup,
                    "hot_ratio": round(hot_ratio, 4),
                    "f1_edge_count": f1_count,
                    "p99_query_us": round(_p99(adapt_query_us), 2) if adapt_query_us else 0.0,
                },
                "dijkstra": {
                    "avg_insert_us": 0.0,
                    "avg_delete_us": 0.0,
                    "avg_query_us": round(dijk_avg, 2),
                    "p99_query_us": round(_p99(dijk_query_us), 2) if dijk_query_us else 0.0,
                },
                "operations": total_ops,
                "graph_size": n,
                "graph_type": graph_type,
                "zipf_alpha": alpha,
                "scaling_data": scaling_data,
            }
            self._status[benchmark_id] = {"status": "done", "progress": 1.0}
            
            # Save to PostgreSQL
            try:
                from db import save_benchmark_run
                save_benchmark_run(benchmark_id, config, self._results[benchmark_id])
            except Exception as e:
                print(f"[DB WARN] Failed to save benchmark to DB: {e}")

        except Exception as exc:
            self._status[benchmark_id] = {"status": "error", "progress": 0.0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Graph generators (local copies — avoid import from benchmarks package)
# ---------------------------------------------------------------------------

def _generate_initial_graph(graph_type: str, n: int) -> nx.Graph:
    """Generate a networkx graph of `n` nodes for the given type."""
    rng = random.Random(42)

    if graph_type == "social":
        # Barabasi-Albert — power-law degree distribution
        m_param = max(2, min(5, n // 10))
        G = nx.barabasi_albert_graph(n, m_param, seed=42)
        for u, v in G.edges():
            G[u][v]["weight"] = round(rng.uniform(1.0, 10.0), 2)

    elif graph_type == "road":
        # Grid graph with random shortcuts
        side = max(2, int(n ** 0.5))
        G = nx.grid_2d_graph(side, side)
        G = nx.convert_node_labels_to_integers(G)
        for u, v in G.edges():
            G[u][v]["weight"] = round(rng.uniform(1.0, 5.0), 2)
        # Add shortcuts
        nodes = list(G.nodes())
        for _ in range(max(1, n // 20)):
            u = rng.choice(nodes)
            v = rng.choice(nodes)
            if u != v and not G.has_edge(u, v):
                G.add_edge(u, v, weight=round(rng.uniform(0.5, 2.0), 2))

    elif graph_type == "adversarial":
        # Path graph — worst case for skeleton formation
        G = nx.path_graph(n)
        for u, v in G.edges():
            G[u][v]["weight"] = round(rng.uniform(1.0, 10.0), 2)

    else:  # "random"
        m_edges = min(n * 3, n * (n - 1) // 2)
        G = nx.gnm_random_graph(n, m_edges, seed=42)
        for u, v in G.edges():
            G[u][v]["weight"] = round(rng.uniform(1.0, 10.0), 2)

    return G


def _generate_ops(
    G: nx.Graph,
    total_ops: int,
    alpha: float,
    insert_frac: float,
    delete_frac: float,
    query_frac: float,
) -> list[tuple]:
    """Generate a sequence of (op_type, args) tuples."""
    rng = random.Random(42)
    nodes = list(G.nodes())
    if not nodes:
        return []

    # Build Zipf weights over node pairs for queries (hub-biased)
    if len(nodes) >= 4:
        sorted_by_deg = sorted(nodes, key=lambda v: G.degree(v), reverse=True)
        hubs = sorted_by_deg[:max(2, ceil(log2(len(nodes))))]
        pairs = [(s, t) for s in hubs for t in hubs if s != t]
        if not pairs:
            pairs = [(nodes[i], nodes[j]) for i in range(len(nodes)) for j in range(i + 1, min(i + 5, len(nodes)))]
    else:
        pairs = [(nodes[i], nodes[j]) for i in range(len(nodes)) for j in range(i + 1, len(nodes))]

    if not pairs:
        return []

    zipf_w = [1.0 / ((k + 1) ** alpha) for k in range(len(pairs))]
    total_w = sum(zipf_w)
    zipf_w = [w / total_w for w in zipf_w]

    current_edges: set[tuple[int, int]] = {
        (min(u, v), max(u, v)) for u, v in G.edges()
    }

    ops: list[tuple] = []
    for _ in range(total_ops):
        r = rng.random()
        if r < query_frac and pairs:
            pair = rng.choices(pairs, weights=zipf_w, k=1)[0]
            ops.append(("QUERY", pair[0], pair[1]))
        elif r < query_frac + insert_frac and len(nodes) >= 2:
            for _attempt in range(10):
                u = rng.choice(nodes)
                v = rng.choice(nodes)
                if u != v:
                    key = (min(u, v), max(u, v))
                    if key not in current_edges:
                        w = round(rng.uniform(1.0, 10.0), 2)
                        ops.append(("INSERT", u, v, w))
                        current_edges.add(key)
                        break
        elif current_edges:
            key = rng.choice(list(current_edges))
            ops.append(("DELETE", key[0], key[1]))
            current_edges.discard(key)

    return ops


# ---------------------------------------------------------------------------
# Algorithm runners
# ---------------------------------------------------------------------------

def _run_adaptskel_benchmark(
    G_init: nx.Graph,
    ops: list[tuple],
    benchmark_id: str,
    status_store: dict,
    total_ops: int,
) -> tuple[list, list, list, float, int]:
    """Run all ops through AdaptSkelService, return timing lists."""
    from services.adaptskel_service import AdaptSkelService

    svc = AdaptSkelService(config={})

    # Pre-load initial graph
    for u, v, data in G_init.edges(data=True):
        svc.insert(u, v, data.get("weight", 1.0))

    insert_times: list[float] = []
    delete_times: list[float] = []
    query_times: list[float] = []

    for i, op in enumerate(ops):
        if i % max(1, total_ops // 20) == 0:
            status_store[benchmark_id] = {
                "status": "running",
                "progress": round(i / (total_ops * 2), 4),
                "phase": "adaptskel",
            }

        if op[0] == "INSERT":
            _, u, v, w = op
            result = svc.insert(u, v, w)
            insert_times.append(result.get("latency_us", 0))
        elif op[0] == "DELETE":
            _, u, v = op
            result = svc.delete(u, v)
            delete_times.append(result.get("latency_us", 0))
        elif op[0] == "QUERY":
            _, s, t = op
            result = svc.query(s, t)
            query_times.append(result.get("latency_us", 0))

    stats = svc.get_stats()
    hot_ratio = stats.get("hot_query_ratio", 0.0)
    f1_count = stats.get("f1_edge_count", 0)

    return insert_times, delete_times, query_times, hot_ratio, f1_count


def _run_dijkstra_benchmark(
    G_init: nx.Graph,
    ops: list[tuple],
    benchmark_id: str,
    status_store: dict,
    total_ops: int,
) -> tuple[list, list, list]:
    """Run all ops through DijkstraBaseline, return timing lists."""
    dijk = DijkstraBaseline()

    # Pre-load initial graph
    for u, v, data in G_init.edges(data=True):
        dijk.insert(u, v, data.get("weight", 1.0))

    insert_times: list[float] = []
    delete_times: list[float] = []
    query_times: list[float] = []

    for i, op in enumerate(ops):
        if i % max(1, total_ops // 20) == 0:
            status_store[benchmark_id] = {
                "status": "running",
                "progress": round((total_ops + i) / (total_ops * 2), 4),
                "phase": "dijkstra",
            }

        if op[0] == "INSERT":
            _, u, v, w = op
            t0 = time.perf_counter()
            dijk.insert(u, v, w)
            insert_times.append((time.perf_counter() - t0) * 1e6)
        elif op[0] == "DELETE":
            _, u, v = op
            t0 = time.perf_counter()
            dijk.delete(u, v)
            delete_times.append((time.perf_counter() - t0) * 1e6)
        elif op[0] == "QUERY":
            _, s, t = op
            t0 = time.perf_counter()
            dijk.query(s, t)
            query_times.append((time.perf_counter() - t0) * 1e6)

    return insert_times, delete_times, query_times


def _generate_scaling_data(
    base_n: int,
    graph_type: str,
    alpha: float,
    insert_frac: float,
    delete_frac: float,
    query_frac: float,
) -> list[dict]:
    """
    Run quick scaling test at a few sizes around base_n.
    Returns list of {n, adaptskel_avg_us, dijkstra_avg_us, speedup}.
    """
    # Pick 3-4 sizes around base_n (capped for performance)
    sizes = sorted({max(10, base_n // 4), max(10, base_n // 2), base_n})
    # Limit to avoid making the HTTP request very slow
    max_size = min(base_n, 500)
    sizes = [s for s in sizes if s <= max_size]

    scaling: list[dict] = []
    ops_per_size = min(200, base_n * 2)

    for n in sizes:
        try:
            G = _generate_initial_graph(graph_type, n)
            ops = _generate_ops(G, ops_per_size, alpha, insert_frac, delete_frac, query_frac)
            dummy_status: dict = {}
            _, _, adapt_q, _, _ = _run_adaptskel_benchmark(G, ops, "_scale", dummy_status, ops_per_size)
            _, _, dijk_q = _run_dijkstra_benchmark(G, ops, "_scale", dummy_status, ops_per_size)

            a_avg = mean(adapt_q) if adapt_q else 0.001
            d_avg = mean(dijk_q) if dijk_q else 0.001
            scaling.append({
                "n": n,
                "adaptskel_avg_us": round(a_avg, 2),
                "dijkstra_avg_us": round(d_avg, 2),
                "speedup": round(d_avg / a_avg, 2) if a_avg > 0 else 1.0,
            })
        except Exception:
            pass

    return scaling


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _p99(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * 0.99)
    return sorted_v[min(idx, len(sorted_v) - 1)]
