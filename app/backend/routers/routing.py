"""Routing API router — /api/routing/* endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RouteRequest(BaseModel):
    source: int
    target: int


class LinkRequest(BaseModel):
    u: int
    v: int


class SimConfig(BaseModel):
    interval_sec: float = 8.0


# ---------------------------------------------------------------------------
# Lazy instantiation of routing service
# ---------------------------------------------------------------------------

_routing_service = None

def _get_routing_service():
    global _routing_service
    if _routing_service is None:
        from services.routing_service import RoutingService
        _routing_service = RoutingService()
    return _routing_service


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@router.get("/topology")
def get_topology():
    """Retrieve node cities and links mapping for the ISP backbone."""
    svc = _get_routing_service()
    return svc.get_topology()


@router.post("/route")
def compute_route(req: RouteRequest):
    """Find shortest path route between source and target cities."""
    svc = _get_routing_service()
    result = svc.route(req.source, req.target)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/failure")
def manual_failure(req: LinkRequest):
    """Simulate a link failure on the u-v path."""
    svc = _get_routing_service()
    result = svc.simulate_failure(req.u, req.v)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/recovery")
def manual_recovery(req: LinkRequest):
    """Restore a failed link on the u-v path."""
    svc = _get_routing_service()
    result = svc.simulate_recovery(req.u, req.v)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/simulation/start")
def start_simulation(config: SimConfig):
    """Start the background Poisson link failure simulator."""
    svc = _get_routing_service()
    return svc.start_simulation(config.interval_sec)


@router.post("/simulation/stop")
def stop_simulation():
    """Stop the background Poisson link failure simulator."""
    svc = _get_routing_service()
    return svc.stop_simulation()


@router.get("/simulation/status")
def get_simulation_status():
    """Get status and metrics of active simulation."""
    svc = _get_routing_service()
    return {
        "active": svc.sim_active,
        "interval_sec": svc.sim_interval,
        "metrics": svc.metrics
    }
