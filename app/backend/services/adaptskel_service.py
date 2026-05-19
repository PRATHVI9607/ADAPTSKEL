"""
AdaptSkelService — wraps the Python AdaptSkel engine with timing instrumentation.

If the core engine is importable (core/python/adaptskel.py), uses it directly.
Otherwise falls back to a NetworkX-backed implementation that is correct but
not O(log² n).

Real engine API (core/python/adaptskel.py):
  - AdaptSkel(T=None, W=None, B=None)
  - .insert(u, v, w)  → dict with keys: f1_size, f2_size, ldb_pending_decreases …
  - .delete(u, v)     → dict with same keys
  - .query(s, t)      → float (exact distance, or inf)
  - .get_stats()      → dict with keys: n_vertices, n_edges, f1_size, f2_size,
                         promotions, demotions, ldb_pending_decreases, …
  - .get_skeleton_edges() → list[dict]  (u, v, w, heat, layer)
  - .get_heat_scores()    → dict[(u,v) -> int]
"""
from __future__ import annotations

import os
import sys
import time
from math import ceil, log2
from typing import Optional

import networkx as nx

# ---------------------------------------------------------------------------
# Try to import real engine
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'core', 'python'))

try:
    from adaptskel import AdaptSkel as _AdaptSkel  # type: ignore
    HAS_ENGINE = True
except ImportError:
    HAS_ENGINE = False


# ---------------------------------------------------------------------------
# NetworkX fallback implementation
# ---------------------------------------------------------------------------

class _NetworkXEngine:
    """
    Correctness-only fallback using NetworkX Dijkstra.
    Tracks enough internal state to return the same response shape as the
    real engine.  Not O(log² n) — O(E log V) per query.
    """

    def __init__(self, config: dict) -> None:
        self._g: nx.Graph = nx.Graph()
        n = max(config.get("W") or 100, 2)
        self._T: int = config.get("T") or ceil(log2(max(n, 2)))
        self._W: int = config.get("W") or n
        self._B: int = config.get("B") or ceil(log2(max(n, 2)))

        # Heat: edge_key -> heat score
        self._heat: dict[tuple[int, int], int] = {}
        # Skeleton set (hot edges): set of canonical edge keys
        self._skeleton: set[tuple[int, int]] = set()
        # Rolling window of query paths (for heat decay)
        self._window: list[list[tuple[int, int]]] = []
        # Promotion / demotion counters
        self.total_promotions: int = 0
        self.total_demotions: int = 0
        # Delta queue depths (simulated)
        self._pending_decreases: int = 0
        self._pending_increases: int = 0

    def insert(self, u: int, v: int, w: float) -> dict:
        key = (min(u, v), max(u, v))
        if not self._g.has_edge(u, v):
            self._g.add_edge(u, v, weight=w)
            self._heat.setdefault(key, 0)
            self._pending_decreases = max(0, self._pending_decreases - self._B + 1)
        in_f1 = key in self._skeleton
        heat_score = self._heat.get(key, 0)
        return {
            "success": True,
            "in_f1": in_f1,
            "heat_score": heat_score,
            "f1_edge_count": len(self._skeleton),
            "delta_queue_depth": self._pending_decreases,
        }

    def delete(self, u: int, v: int) -> dict:
        key = (min(u, v), max(u, v))
        was_skeleton = key in self._skeleton
        if self._g.has_edge(u, v):
            self._g.remove_edge(u, v)
        self._skeleton.discard(key)
        self._heat.pop(key, None)
        replacement_found = False
        if was_skeleton:
            replacement_found = nx.is_connected(self._g) if len(self._g.nodes) > 0 else False
            self._pending_increases = max(0, self._pending_increases + 1)
        return {
            "success": True,
            "was_skeleton": was_skeleton,
            "replacement_found": replacement_found,
        }

    def query(self, s: int, t: int) -> dict:
        if s not in self._g or t not in self._g:
            return {
                "distance": float("inf"),
                "path": [],
                "path_hot": False,
                "newly_promoted": 0,
            }
        try:
            dist = nx.shortest_path_length(self._g, s, t, weight="weight")
            path = nx.shortest_path(self._g, s, t, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return {
                "distance": float("inf"),
                "path": [],
                "path_hot": False,
                "newly_promoted": 0,
            }

        path_edges = [(min(path[i], path[i + 1]), max(path[i], path[i + 1]))
                      for i in range(len(path) - 1)]

        newly_promoted = 0
        for key in path_edges:
            self._heat[key] = self._heat.get(key, 0) + 1
            if self._heat[key] >= self._T and key not in self._skeleton:
                self._skeleton.add(key)
                self.total_promotions += 1
                newly_promoted += 1

        self._window.append(path_edges)
        if len(self._window) > self._W:
            old_path = self._window.pop(0)
            for key in old_path:
                if key in self._heat:
                    self._heat[key] -= 1
                    if self._heat[key] <= self._T // 2 and key in self._skeleton:
                        self._skeleton.discard(key)
                        self.total_demotions += 1

        path_hot = all(k in self._skeleton for k in path_edges) if path_edges else False
        self._pending_increases = max(0, self._pending_increases - 1)

        return {
            "distance": dist,
            "path": path,
            "path_hot": path_hot,
            "newly_promoted": newly_promoted,
        }

    def get_stats(self) -> dict:
        f1 = len(self._skeleton)
        total_e = self._g.number_of_edges()
        return {
            "vertex_count": self._g.number_of_nodes(),
            "edge_count": total_e,
            "f1_edge_count": f1,
            "f2_edge_count": max(0, total_e - f1),
            "total_promotions": self.total_promotions,
            "total_demotions": self.total_demotions,
            "pending_decreases": self._pending_decreases,
            "pending_increases": self._pending_increases,
        }

    def get_skeleton(self) -> list[dict]:
        edges = []
        for key in self._skeleton:
            u, v = key
            w = self._g[u][v]["weight"] if self._g.has_edge(u, v) else 0.0
            edges.append({
                "u": u,
                "v": v,
                "w": w,
                "heat": self._heat.get(key, 0),
                "is_spanning": True,
            })
        return edges

    def get_heat(self) -> dict[str, int]:
        return {f"{u}-{v}": h for (u, v), h in self._heat.items()}


# ---------------------------------------------------------------------------
# AdaptSkelService — main wrapper
# ---------------------------------------------------------------------------

class AdaptSkelService:
    """
    Service wrapper around the AdaptSkel engine (real or NX fallback).
    Adds per-operation timing instrumentation and exposes a unified
    dict-returning API used by the routers.
    """

    def __init__(self, config: dict = None) -> None:
        config = config or {}

        if HAS_ENGINE:
            try:
                kwargs: dict = {}
                if config.get("T") is not None:
                    kwargs["T"] = int(config["T"])
                if config.get("W") is not None:
                    kwargs["W"] = int(config["W"])
                if config.get("B") is not None:
                    kwargs["B"] = int(config["B"])
                self._engine = _AdaptSkel(**kwargs)
                self._use_real = True
            except Exception:
                self._engine = _NetworkXEngine(config)
                self._use_real = False
        else:
            self._engine = _NetworkXEngine(config)
            self._use_real = False

        self._insert_times: list[float] = []
        self._delete_times: list[float] = []
        self._query_times: list[float] = []
        self._hot_queries: int = 0
        self._total_queries: int = 0

    # ------------------------------------------------------------------
    # Core operations with timing
    # ------------------------------------------------------------------

    def insert(self, u: int, v: int, w: float) -> dict:
        t0 = time.perf_counter()

        if self._use_real:
            # Real engine insert() returns a full stats dict
            raw = self._engine.insert(u, v, w)
            latency_us = (time.perf_counter() - t0) * 1e6
            result = {
                "success": True,
                "in_f1": raw.get("f1_size", 0) > 0,
                "heat_score": 0,
                "f1_edge_count": raw.get("f1_size", 0),
                "delta_queue_depth": raw.get("ldb_pending_decreases", 0),
                "latency_us": round(latency_us, 1),
            }
        else:
            result = self._engine.insert(u, v, w)
            latency_us = (time.perf_counter() - t0) * 1e6
            result["latency_us"] = round(latency_us, 1)

        self._insert_times.append(latency_us)
        return result

    def delete(self, u: int, v: int) -> dict:
        t0 = time.perf_counter()

        if self._use_real:
            # Real engine delete() returns a full stats dict
            raw = self._engine.delete(u, v)
            latency_us = (time.perf_counter() - t0) * 1e6
            result = {
                "success": True,
                "was_skeleton": False,   # real engine doesn't expose this yet
                "replacement_found": False,
                "latency_us": round(latency_us, 1),
            }
        else:
            result = self._engine.delete(u, v)
            latency_us = (time.perf_counter() - t0) * 1e6
            result["latency_us"] = round(latency_us, 1)

        self._delete_times.append(latency_us)
        return result

    def query(self, s: int, t: int) -> dict:
        t0 = time.perf_counter()

        if self._use_real:
            # Real engine query() returns a float (exact distance or inf)
            dist = self._engine.query(s, t)
            latency_us = (time.perf_counter() - t0) * 1e6
            result = {
                "distance": dist if dist != float("inf") else None,
                "path": [],
                "path_hot": False,
                "newly_promoted": 0,
                "latency_us": round(latency_us, 1),
            }
        else:
            result = self._engine.query(s, t)
            latency_us = (time.perf_counter() - t0) * 1e6
            result["latency_us"] = round(latency_us, 1)
            if result.get("distance") == float("inf"):
                result["distance"] = None

        self._query_times.append(latency_us)
        self._total_queries += 1
        if result.get("path_hot"):
            self._hot_queries += 1

        return result

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        hot_ratio = (self._hot_queries / self._total_queries) if self._total_queries > 0 else 0.0
        avg_insert = _mean(self._insert_times)
        avg_delete = _mean(self._delete_times)
        avg_query = _mean(self._query_times)

        if self._use_real:
            try:
                # Real engine returns keys: n_vertices, n_edges, f1_size, f2_size,
                #   promotions, demotions, ldb_pending_decreases, ldb_pending_increases
                raw = self._engine.get_stats()
                return {
                    "vertex_count": raw.get("n_vertices", 0),
                    "edge_count": raw.get("n_edges", 0),
                    "f1_edge_count": raw.get("f1_size", 0),
                    "f2_edge_count": raw.get("f2_size", 0),
                    "hot_query_ratio": round(hot_ratio, 4),
                    "avg_insert_us": round(avg_insert, 2),
                    "avg_delete_us": round(avg_delete, 2),
                    "avg_query_us": round(avg_query, 2),
                    "total_promotions": raw.get("promotions", 0),
                    "total_demotions": raw.get("demotions", 0),
                    "pending_decreases": raw.get("ldb_pending_decreases", 0),
                    "pending_increases": raw.get("ldb_pending_increases", 0),
                }
            except Exception:
                pass  # Fall through to NX fallback stats

        raw = self._engine.get_stats()
        return {
            "vertex_count": raw.get("vertex_count", 0),
            "edge_count": raw.get("edge_count", 0),
            "f1_edge_count": raw.get("f1_edge_count", 0),
            "f2_edge_count": raw.get("f2_edge_count", 0),
            "hot_query_ratio": round(hot_ratio, 4),
            "avg_insert_us": round(avg_insert, 2),
            "avg_delete_us": round(avg_delete, 2),
            "avg_query_us": round(avg_query, 2),
            "total_promotions": raw.get("total_promotions", 0),
            "total_demotions": raw.get("total_demotions", 0),
            "pending_decreases": raw.get("pending_decreases", 0),
            "pending_increases": raw.get("pending_increases", 0),
        }

    # ------------------------------------------------------------------
    # Skeleton / heat
    # ------------------------------------------------------------------

    def get_skeleton(self) -> list[dict]:
        if self._use_real:
            try:
                # Real engine method: get_skeleton_edges() -> list[dict]
                raw_edges = self._engine.get_skeleton_edges()
                for e in raw_edges:
                    e.setdefault("is_spanning", True)
                return raw_edges
            except Exception:
                return []
        return self._engine.get_skeleton()

    def get_heat(self) -> dict[str, int]:
        if self._use_real:
            try:
                # Real engine method: get_heat_scores() -> dict[(u,v) -> int]
                raw_scores = self._engine.get_heat_scores()
                return {f"{u}-{v}": h for (u, v), h in raw_scores.items()}
            except Exception:
                return {}
        return self._engine.get_heat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
