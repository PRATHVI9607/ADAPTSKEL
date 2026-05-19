"""Benchmark API router — /api/benchmark/* endpoints."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class QueryMix(BaseModel):
    insert: float = 0.2
    delete: float = 0.1
    query: float = 0.7


class BenchmarkRunRequest(BaseModel):
    graph_type: str = "random"   # "random" | "road" | "social" | "adversarial"
    node_count: int = 100
    operations: int = 1000
    query_mix: QueryMix = QueryMix()
    zipf_alpha: float = 1.2


# ---------------------------------------------------------------------------
# Lazy import of benchmark service
# ---------------------------------------------------------------------------

_benchmark_service = None


def _get_benchmark_service():
    global _benchmark_service
    if _benchmark_service is None:
        from services.benchmark_service import BenchmarkService
        _benchmark_service = BenchmarkService()
    return _benchmark_service


# ---------------------------------------------------------------------------
# POST /api/benchmark/run
# ---------------------------------------------------------------------------

@router.post("/run")
def run_benchmark(req: BenchmarkRunRequest):
    """Start a benchmark run in a background thread. Returns benchmark_id."""
    svc = _get_benchmark_service()
    benchmark_id = "b_" + uuid.uuid4().hex[:8]

    config = {
        "graph_type": req.graph_type,
        "node_count": req.node_count,
        "operations": req.operations,
        "query_mix": {
            "insert": req.query_mix.insert,
            "delete": req.query_mix.delete,
            "query": req.query_mix.query,
        },
        "zipf_alpha": req.zipf_alpha,
    }

    svc.start_benchmark(benchmark_id, config)
    return {"benchmark_id": benchmark_id}


# ---------------------------------------------------------------------------
# GET /api/benchmark/{id}/status
# ---------------------------------------------------------------------------

@router.get("/{benchmark_id}/status")
def get_status(benchmark_id: str):
    """Return current status and progress of a benchmark run."""
    svc = _get_benchmark_service()
    status = svc.get_status(benchmark_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found")
    return status


# ---------------------------------------------------------------------------
# GET /api/benchmark/{id}/results
# ---------------------------------------------------------------------------

@router.get("/{benchmark_id}/results")
def get_results(benchmark_id: str):
    """Return completed benchmark results."""
    svc = _get_benchmark_service()
    status = svc.get_status(benchmark_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found")
    if status.get("status") == "running":
        raise HTTPException(status_code=202, detail="Benchmark still running")
    results = svc.get_results(benchmark_id)
    if not results:
        raise HTTPException(status_code=404, detail="No results available")
    return results
