"""ADAPTSKEL Backend API"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uuid
import sys
import os

# Add core/python to path so AdaptSkel engine is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core', 'python'))
# Add app/backend to path so local routers and services are importable
sys.path.insert(0, os.path.dirname(__file__))

app = FastAPI(title="ADAPTSKEL API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory graph store: graph_id -> AdaptSkelService instance
graph_store: dict = {}
# networkx graph mirror for oracle verification: graph_id -> nx.Graph
graph_nx_store: dict = {}

from routers import graph, benchmark, routing
from db import init_db

app.include_router(graph.router, prefix="/api/graph")
app.include_router(benchmark.router, prefix="/api/benchmark")
app.include_router(routing.router, prefix="/api/routing")


@app.on_event("startup")
def startup_event():
    init_db()


@app.on_event("shutdown")
def shutdown_event():
    # Stop any background routing simulation thread
    try:
        from routers.routing import _get_routing_service
        svc = _get_routing_service()
        if svc:
            svc.stop_simulation()
    except Exception:
        pass


@app.get("/health")
def health():
    return {"status": "ok", "graphs": len(graph_store)}

