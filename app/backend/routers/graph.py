"""Graph API router — all /api/graph/* endpoints including WebSocket streaming."""
from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from math import ceil, log2
from typing import Optional

import networkx as nx
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

# Shared graph stores imported from main module at runtime to avoid circular imports
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'core', 'python'))

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class GraphConfig(BaseModel):
    T: Optional[float] = None
    W: Optional[int] = None
    B: Optional[int] = None


class CreateGraphRequest(BaseModel):
    config: GraphConfig = GraphConfig()


class InsertEdgeRequest(BaseModel):
    u: int
    v: int
    w: float


class QueryRequest(BaseModel):
    source: int
    target: int


class PresetRequest(BaseModel):
    preset: str = "random"
    n: int = 20


# ---------------------------------------------------------------------------
# Lazy import of stores from main to avoid circular import
# ---------------------------------------------------------------------------

def _get_stores():
    """Return (graph_store, graph_nx_store) from the running app."""
    import main as _main
    return _main.graph_store, _main.graph_nx_store


def _get_service(graph_id: str):
    """Retrieve AdaptSkelService or raise 404."""
    store, _ = _get_stores()
    svc = store.get(graph_id)
    if svc is None:
        raise HTTPException(status_code=404, detail=f"Graph '{graph_id}' not found")
    return svc


def _get_nx(graph_id: str) -> nx.Graph:
    _, nx_store = _get_stores()
    g = nx_store.get(graph_id)
    if g is None:
        raise HTTPException(status_code=404, detail=f"Graph '{graph_id}' not found")
    return g


# ---------------------------------------------------------------------------
# Endpoint: POST /api/graph/create
# ---------------------------------------------------------------------------

@router.post("/create")
def create_graph(req: CreateGraphRequest):
    """Create a new graph instance, return its ID."""
    from services.adaptskel_service import AdaptSkelService

    graph_id = "g_" + uuid.uuid4().hex[:8]
    config = req.config.model_dump()
    svc = AdaptSkelService(config=config)

    store, nx_store = _get_stores()
    store[graph_id] = svc
    nx_store[graph_id] = nx.Graph()

    return {"graph_id": graph_id}


# ---------------------------------------------------------------------------
# Endpoint: POST /api/graph/{id}/insert
# ---------------------------------------------------------------------------

@router.post("/{graph_id}/insert")
def insert_edge(graph_id: str, req: InsertEdgeRequest):
    """Insert edge (u, v, w) into the graph."""
    svc = _get_service(graph_id)
    nx_g = _get_nx(graph_id)

    result = svc.insert(req.u, req.v, req.w)

    # Mirror in networkx oracle
    nx_g.add_edge(req.u, req.v, weight=req.w)

    return result


# ---------------------------------------------------------------------------
# Endpoint: DELETE /api/graph/{id}/edge/{u}/{v}
# ---------------------------------------------------------------------------

@router.delete("/{graph_id}/edge/{u}/{v}")
def delete_edge(graph_id: str, u: int, v: int):
    """Delete edge (u, v) from the graph."""
    svc = _get_service(graph_id)
    nx_g = _get_nx(graph_id)

    result = svc.delete(u, v)

    # Mirror in networkx oracle (ignore if not present)
    if nx_g.has_edge(u, v):
        nx_g.remove_edge(u, v)

    return result


# ---------------------------------------------------------------------------
# Endpoint: POST /api/graph/{id}/query
# ---------------------------------------------------------------------------

@router.post("/{graph_id}/query")
def query_path(graph_id: str, req: QueryRequest):
    """Return shortest-path distance and path from source to target."""
    svc = _get_service(graph_id)
    return svc.query(req.source, req.target)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/graph/{id}/stats
# ---------------------------------------------------------------------------

@router.get("/{graph_id}/stats")
def get_stats(graph_id: str):
    """Return engine statistics."""
    svc = _get_service(graph_id)
    return svc.get_stats()


# ---------------------------------------------------------------------------
# Endpoint: GET /api/graph/{id}/skeleton
# ---------------------------------------------------------------------------

@router.get("/{graph_id}/skeleton")
def get_skeleton(graph_id: str):
    """Return the F1 skeleton edge list with heat scores."""
    svc = _get_service(graph_id)
    edges = svc.get_skeleton()
    return {"edges": edges}


# ---------------------------------------------------------------------------
# Endpoint: GET /api/graph/{id}/heat
# ---------------------------------------------------------------------------

@router.get("/{graph_id}/heat")
def get_heat(graph_id: str):
    """Return all edge heat scores as a {edge_key: score} dict."""
    svc = _get_service(graph_id)
    scores = svc.get_heat()
    return {"scores": scores}


# ---------------------------------------------------------------------------
# Endpoint: POST /api/graph/{id}/preset
# ---------------------------------------------------------------------------

@router.post("/{graph_id}/preset")
def load_preset(graph_id: str, req: PresetRequest):
    """Populate graph with a preset random topology."""
    svc = _get_service(graph_id)
    nx_g = _get_nx(graph_id)

    # Edge density per preset type
    prob = {"random": 0.25, "road": 0.15, "social": 0.20, "adversarial": 0.30}.get(req.preset, 0.25)
    edge_count = 0
    for u in range(req.n):
        for v in range(u + 1, req.n):
            if random.random() < prob:
                w = round(random.uniform(1.0, 20.0), 1)
                try:
                    svc.insert(u, v, w)
                    nx_g.add_edge(u, v, weight=w)
                    edge_count += 1
                except Exception:
                    pass
    return {"preset": req.preset, "n": req.n, "edges": edge_count}


# ---------------------------------------------------------------------------
# WebSocket: WS /api/graph/{id}/stream
# ---------------------------------------------------------------------------

# Speed → sleep duration between operations (seconds)
_SPEED_DELAY = {
    "slow":   0.5,
    "normal": 0.1,
    "fast":   0.02,
    "max":    0.0,
}


@router.websocket("/{graph_id}/stream")
async def stream_graph(websocket: WebSocket, graph_id: str):
    """
    WebSocket endpoint that streams graph events to the client.

    Client sends:
        { "type": "START", "speed": "normal" }
        { "type": "STOP" }

    Server sends a continuous stream of INSERT / DELETE / QUERY / PROMOTE /
    DEMOTE / STATS messages at the requested speed.
    """
    await websocket.accept()

    store, nx_store = _get_stores()
    if graph_id not in store:
        await websocket.send_json({"type": "ERROR", "message": f"Graph '{graph_id}' not found"})
        await websocket.close()
        return

    svc = store[graph_id]
    nx_g = nx_store[graph_id]

    streaming = False
    speed = "normal"
    delay = _SPEED_DELAY["normal"]

    # Track local edge set for random workload generation
    local_edges: list[tuple[int, int, float]] = []
    node_count = 50  # start with 50 virtual nodes for the demo workload

    async def _generate_and_send():
        """Generate one random graph operation, apply it, and send the event."""
        nonlocal local_edges

        r = random.random()

        if r < 0.35:
            # INSERT
            u = random.randint(0, node_count - 1)
            v = random.randint(0, node_count - 1)
            if u == v:
                return
            # Avoid duplicates
            existing_keys = {(min(a, b), max(a, b)) for a, b, _ in local_edges}
            key = (min(u, v), max(u, v))
            if key in existing_keys:
                return
            w = round(random.uniform(1.0, 10.0), 2)
            result = svc.insert(u, v, w)
            nx_g.add_edge(u, v, weight=w)
            local_edges.append((u, v, w))
            heat_score = result.get("heat_score", 0)
            await websocket.send_json({
                "type": "INSERT",
                "u": u,
                "v": v,
                "w": w,
                "in_f1": result.get("in_f1", False),
                "heat": heat_score,
            })

        elif r < 0.50 and local_edges:
            # DELETE
            idx = random.randrange(len(local_edges))
            u, v, w = local_edges[idx]
            result = svc.delete(u, v)
            if nx_g.has_edge(u, v):
                nx_g.remove_edge(u, v)
            local_edges.pop(idx)
            await websocket.send_json({
                "type": "DELETE",
                "u": u,
                "v": v,
            })

        elif r < 0.85:
            # QUERY
            if node_count < 2:
                return
            s = random.randint(0, node_count - 1)
            t = random.randint(0, node_count - 1)
            if s == t:
                return
            result = svc.query(s, t)
            await websocket.send_json({
                "type": "QUERY",
                "s": s,
                "t": t,
                "path": result.get("path", []),
                "distance": result.get("distance", float("inf")),
                "hot": result.get("path_hot", False),
                "latency_us": result.get("latency_us", 0),
            })

        else:
            # STATS broadcast
            stats = svc.get_stats()
            await websocket.send_json({
                "type": "STATS",
                "ops_per_sec": _estimate_ops_per_sec(svc),
                "hot_ratio": stats.get("hot_query_ratio", 0.0),
                "f1_edges": stats.get("f1_edge_count", 0),
                "delta_queue": stats.get("pending_decreases", 0) + stats.get("pending_increases", 0),
            })

    # Track timing for ops/sec estimation
    _op_times: list[float] = []

    def _estimate_ops_per_sec(svc) -> float:
        now = time.monotonic()
        _op_times.append(now)
        # Keep only last 100 timestamps
        while len(_op_times) > 100:
            _op_times.pop(0)
        if len(_op_times) < 2:
            return 0.0
        elapsed = _op_times[-1] - _op_times[0]
        if elapsed <= 0:
            return 0.0
        return round(len(_op_times) / elapsed, 1)

    try:
        while True:
            # Non-blocking receive with timeout so we can keep streaming
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=delay if streaming else None)
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "START":
                    speed = msg.get("speed", "normal").lower()
                    delay = _SPEED_DELAY.get(speed, 0.1)
                    streaming = True
                elif msg_type == "STOP":
                    streaming = False
                elif msg_type == "SET_SPEED":
                    speed = msg.get("speed", "normal").lower()
                    delay = _SPEED_DELAY.get(speed, 0.1)

            except asyncio.TimeoutError:
                pass  # No message received — continue streaming

            if streaming:
                await _generate_and_send()
                if delay > 0:
                    await asyncio.sleep(delay)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "ERROR", "message": str(exc)})
        except Exception:
            pass
