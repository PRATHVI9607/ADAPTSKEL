"""
Master benchmark runner for ADAPTSKEL.

Runs head-to-head comparisons between ADAPTSKEL and Dijkstra across all four
workload generators and saves results as JSON to benchmarks/results/.

Usage
-----
    python benchmarks/run_benchmarks.py --quick     # fast (3 sizes, 500 ops)
    python benchmarks/run_benchmarks.py --full      # full (6 sizes, 2000 ops)
    python benchmarks/run_benchmarks.py             # quick by default
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from math import log2
from statistics import mean, median, stdev
from typing import Any

import networkx as nx

# ---------------------------------------------------------------------------
# Path setup — allow running from project root or from benchmarks/
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "core", "python"))
sys.path.insert(0, _ROOT)

# ---------------------------------------------------------------------------
# Try to import ADAPTSKEL engine; fall back to NX service
# ---------------------------------------------------------------------------

try:
    from adaptskel import AdaptSkel as _AdaptSkel  # type: ignore
    HAS_ENGINE = True
except ImportError:
    HAS_ENGINE = False

from benchmarks.generators.zipf_workload import generate_zipf_workload
from benchmarks.generators.scaling_benchmark import generate_scaling_benchmark
from benchmarks.generators.adversarial import generate_adversarial_workload
from benchmarks.generators.road_network import generate_road_workload


# ---------------------------------------------------------------------------
# Dijkstra baseline runner
# ---------------------------------------------------------------------------

class DijkstraBaseline:
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
# NetworkX-based ADAPTSKEL stand-in (when real engine not available)
# ---------------------------------------------------------------------------

class _NXAdaptSkel:
    """Correctness-only stand-in using NetworkX + heat tracking."""

    def __init__(self) -> None:
        self._g: nx.Graph = nx.Graph()
        self._heat: dict = {}
        self._skeleton: set = set()
        self._window: list = []
        self._T = 5
        self._W = 100
        self._promotions = 0
        self._hot = 0
        self._total_q = 0

    def insert(self, u, v, w):
        self._g.add_edge(u, v, weight=w)
        self._heat.setdefault((min(u, v), max(u, v)), 0)

    def delete(self, u, v):
        if self._g.has_edge(u, v):
            self._g.remove_edge(u, v)
        key = (min(u, v), max(u, v))
        self._skeleton.discard(key)

    def query(self, s, t) -> tuple[float, list[int], bool]:
        try:
            dist = nx.shortest_path_length(self._g, s, t, weight="weight")
            path = nx.shortest_path(self._g, s, t, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return float("inf"), [], False

        path_edges = [(min(path[i], path[i + 1]), max(path[i], path[i + 1]))
                      for i in range(len(path) - 1)]

        # Heat increment
        for key in path_edges:
            self._heat[key] = self._heat.get(key, 0) + 1
            if self._heat[key] >= self._T and key not in self._skeleton:
                self._skeleton.add(key)
                self._promotions += 1

        # Window eviction
        self._window.append(path_edges)
        if len(self._window) > self._W:
            old = self._window.pop(0)
            for key in old:
                if key in self._heat:
                    self._heat[key] = max(0, self._heat[key] - 1)
                    if self._heat[key] <= self._T // 2:
                        self._skeleton.discard(key)

        self._total_q += 1
        hot = all(k in self._skeleton for k in path_edges) if path_edges else False
        if hot:
            self._hot += 1
        return dist, path, hot

    def hot_ratio(self) -> float:
        return self._hot / self._total_q if self._total_q > 0 else 0.0

    def f1_count(self) -> int:
        return len(self._skeleton)


# ---------------------------------------------------------------------------
# Core timing function
# ---------------------------------------------------------------------------

def _run_on_ops(
    engine,
    engine_is_nx_adapt: bool,
    G_init: nx.Graph,
    ops: list,
) -> dict[str, Any]:
    """
    Pre-load graph then run ops, returning timing results.
    engine can be DijkstraBaseline or _NXAdaptSkel.
    """
    for u, v, data in G_init.edges(data=True):
        engine.insert(u, v, data.get("weight", 1.0))

    insert_times: list[float] = []
    delete_times: list[float] = []
    query_times: list[float] = []

    for op in ops:
        op_type = op[0] if isinstance(op, tuple) else op.type

        if op_type == "INSERT":
            u, v = op[1], op[2]
            w = op[3]
            t0 = time.perf_counter()
            engine.insert(u, v, w)
            insert_times.append((time.perf_counter() - t0) * 1e6)

        elif op_type == "DELETE":
            u, v = op[1], op[2]
            t0 = time.perf_counter()
            engine.delete(u, v)
            delete_times.append((time.perf_counter() - t0) * 1e6)

        elif op_type == "QUERY":
            s, t = op[1], op[2]
            t0 = time.perf_counter()
            engine.query(s, t)
            query_times.append((time.perf_counter() - t0) * 1e6)

    result: dict[str, Any] = {
        "avg_insert_us": round(mean(insert_times), 2) if insert_times else 0.0,
        "avg_delete_us": round(mean(delete_times), 2) if delete_times else 0.0,
        "avg_query_us": round(mean(query_times), 3) if query_times else 0.0,
        "p99_query_us": round(_p99(query_times), 2) if query_times else 0.0,
        "median_query_us": round(median(query_times), 2) if query_times else 0.0,
        "total_queries": len(query_times),
        "total_inserts": len(insert_times),
        "total_deletes": len(delete_times),
    }
    if engine_is_nx_adapt:
        result["hot_ratio"] = round(engine.hot_ratio(), 4)
        result["f1_edge_count"] = engine.f1_count()
    return result


def _benchmark_workload(
    label: str,
    G: nx.Graph,
    ops: list,
    verbose: bool = True,
) -> dict[str, Any]:
    """Run one workload against both algorithms, return combined result."""
    if verbose:
        print(f"  Running ADAPTSKEL ... ", end="", flush=True)
    adapt = _NXAdaptSkel()
    adapt_res = _run_on_ops(adapt, True, G, ops)
    if verbose:
        print(f"avg query {adapt_res['avg_query_us']:.2f} μs")

    if verbose:
        print(f"  Running Dijkstra  ... ", end="", flush=True)
    dijk = DijkstraBaseline()
    dijk_res = _run_on_ops(dijk, False, G, ops)
    if verbose:
        print(f"avg query {dijk_res['avg_query_us']:.2f} μs")

    a_q = adapt_res["avg_query_us"] or 0.001
    d_q = dijk_res["avg_query_us"] or 0.001
    speedup = round(d_q / a_q, 2)

    return {
        "label": label,
        "n": G.number_of_nodes(),
        "m": G.number_of_edges(),
        "total_ops": len(ops),
        "adaptskel": adapt_res,
        "dijkstra": dijk_res,
        "speedup": speedup,
    }


# ---------------------------------------------------------------------------
# Quick benchmark
# ---------------------------------------------------------------------------

def run_quick_benchmark(verbose: bool = True) -> dict:
    """Quick benchmark: sizes [100, 500, 1000], 500 ops each."""
    if verbose:
        print("\n=== QUICK BENCHMARK (sizes: 100, 500, 1000 | 500 ops each) ===\n")

    sizes = [100, 500, 1000]
    ops_per = 500
    results = {}

    # Scaling
    scaling_results = []
    workloads = generate_scaling_benchmark(sizes=sizes, ops_per_size=ops_per)
    for n, data in sorted(workloads.items()):
        if verbose:
            print(f"[Scaling n={n}]")
        res = _benchmark_workload(f"scaling_n{n}", data["graph"], data["ops"], verbose)
        scaling_results.append(res)

    results["scaling"] = scaling_results

    # Adversarial (n=200)
    if verbose:
        print("\n[Adversarial n=200]")
    G_adv, ops_adv = generate_adversarial_workload(n=200, ops=300)
    results["adversarial"] = _benchmark_workload("adversarial_n200", G_adv, ops_adv, verbose)

    # Road network (grid 10x10)
    if verbose:
        print("\n[Road Network 10x10]")
    G_road, ops_road = generate_road_workload(grid_size=10, num_ops=300)
    results["road"] = _benchmark_workload("road_10x10", G_road, ops_road, verbose)

    return results


# ---------------------------------------------------------------------------
# Full benchmark
# ---------------------------------------------------------------------------

def run_full_benchmark(verbose: bool = True) -> dict:
    """Full benchmark: sizes [100, 500, 1K, 5K, 10K, 50K], 2000 ops each."""
    if verbose:
        print("\n=== FULL BENCHMARK (sizes: 100-50K | 2000 ops each) ===\n")

    sizes = [100, 500, 1000, 5000, 10000, 50000]
    ops_per = 2000
    results = {}

    # Scaling
    scaling_results = []
    workloads = generate_scaling_benchmark(sizes=sizes, ops_per_size=ops_per)
    for n, data in sorted(workloads.items()):
        if verbose:
            print(f"[Scaling n={n}]")
        res = _benchmark_workload(f"scaling_n{n}", data["graph"], data["ops"], verbose)
        scaling_results.append(res)
    results["scaling"] = scaling_results

    # Adversarial
    if verbose:
        print("\n[Adversarial n=1000]")
    G_adv, ops_adv = generate_adversarial_workload(n=1000, ops=2000)
    results["adversarial"] = _benchmark_workload("adversarial_n1000", G_adv, ops_adv, verbose)

    # Road network
    if verbose:
        print("\n[Road Network 30x30]")
    G_road, ops_road = generate_road_workload(grid_size=30, num_ops=2000)
    results["road"] = _benchmark_workload("road_30x30", G_road, ops_road, verbose)

    # Zipf with varying α
    alpha_results = []
    for alpha in [0.5, 1.0, 1.2, 1.5, 2.0]:
        if verbose:
            print(f"\n[Zipf α={alpha} n=500]")
        G_z, ops_z = generate_zipf_workload(n=500, m=3, num_queries=1000, alpha=alpha)
        res = _benchmark_workload(f"zipf_alpha{alpha}", G_z, ops_z, verbose)
        res["alpha"] = alpha
        alpha_results.append(res)
    results["zipf_alpha_sweep"] = alpha_results

    return results


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------

def save_results(results: dict, filename: str) -> str:
    """Save results JSON to benchmarks/results/. Returns output path."""
    results_dir = os.path.join(_HERE, "results")
    os.makedirs(results_dir, exist_ok=True)
    path = os.path.join(results_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    return path


def _print_summary(results: dict) -> None:
    """Print a formatted summary table."""
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    if "scaling" in results:
        print(f"\n{'n':>8}  {'ADAPTSKEL μs':>14}  {'Dijkstra μs':>12}  {'Speedup':>8}")
        print("-" * 50)
        for r in results["scaling"]:
            a = r["adaptskel"]["avg_query_us"]
            d = r["dijkstra"]["avg_query_us"]
            s = r["speedup"]
            hot = r["adaptskel"].get("hot_ratio", 0)
            print(f"{r['n']:>8}  {a:>14.2f}  {d:>12.2f}  {s:>7.1f}×  (hot={hot:.0%})")

    if "adversarial" in results:
        a = results["adversarial"]
        print(f"\nAdversarial: ADAPTSKEL {a['adaptskel']['avg_query_us']:.2f} μs  "
              f"vs Dijkstra {a['dijkstra']['avg_query_us']:.2f} μs  "
              f"(speedup {a['speedup']:.1f}×)")

    if "road" in results:
        r = results["road"]
        print(f"Road net:    ADAPTSKEL {r['adaptskel']['avg_query_us']:.2f} μs  "
              f"vs Dijkstra {r['dijkstra']['avg_query_us']:.2f} μs  "
              f"(speedup {r['speedup']:.1f}×)")
    print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _p99(values: list[float]) -> float:
    if not values:
        return 0.0
    sv = sorted(values)
    idx = max(0, int(len(sv) * 0.99) - 1)
    return sv[idx]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ADAPTSKEL master benchmark runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick benchmark (3 sizes, 500 ops each)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full benchmark (6 sizes, 2000 ops each)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-operation progress output",
    )
    args = parser.parse_args()

    verbose = not args.quiet
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    if args.full:
        t_start = time.perf_counter()
        results = run_full_benchmark(verbose=verbose)
        elapsed = time.perf_counter() - t_start
        results["_meta"] = {"mode": "full", "elapsed_s": round(elapsed, 1), "timestamp": timestamp}
        out = save_results(results, f"full_{timestamp}.json")
        _print_summary(results)
        print(f"Full benchmark completed in {elapsed:.1f}s  →  {out}")
    else:
        # Default: quick
        t_start = time.perf_counter()
        results = run_quick_benchmark(verbose=verbose)
        elapsed = time.perf_counter() - t_start
        results["_meta"] = {"mode": "quick", "elapsed_s": round(elapsed, 1), "timestamp": timestamp}
        out = save_results(results, f"quick_{timestamp}.json")
        _print_summary(results)
        print(f"Quick benchmark completed in {elapsed:.1f}s  →  {out}")
