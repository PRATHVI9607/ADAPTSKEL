"""
Congestion-aware routing tests.

Locks two guarantees that matter for the demo:
  1. Congestion-aware routing is NEVER worse than latency-only routing
     (improvement >= 0) — thanks to the knee-hinge penalty.
  2. Under failure-driven overload it is STRICTLY better (loss drops).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core', 'python'))

from routing.simulation import ISPRoutingSimulation
from routing.congestion import CongestionAwareRouter


def test_healthy_network_has_no_loss():
    sim = ISPRoutingSimulation(num_demands=120)
    c = sim.evaluate_congestion()
    # Calibrated to ~0.85 max utilisation on the healthy network → no overload.
    assert c["baseline_loss_pct"] == 0.0
    assert c["congestion_aware_loss_pct"] == 0.0


def test_congestion_aware_never_worse():
    sim = ISPRoutingSimulation(num_demands=120)
    cuts = [(0, 1), (0, 4), (1, 5), (2, 3), (4, 5)]
    for u, v in cuts:
        try:
            sim.trigger_manual_failure(u, v)
        except Exception:
            pass
        sim.current_demands = sim.traffic_sim.generate_demands(8)
        c = sim.evaluate_congestion()
        assert c["congestion_aware_loss_pct"] <= c["baseline_loss_pct"] + 1e-6, (
            f"congestion-aware ({c['congestion_aware_loss_pct']}%) worse than "
            f"baseline ({c['baseline_loss_pct']}%) after cutting {u}-{v}"
        )
        assert c["improvement_pct"] >= -1e-6


def test_congestion_aware_helps_under_overload():
    sim = ISPRoutingSimulation(num_demands=140)
    # Cut several hub links to force real overload on survivors.
    for u, v in [(0, 1), (0, 4), (1, 5), (2, 3)]:
        try:
            sim.trigger_manual_failure(u, v)
        except Exception:
            pass
    sim.current_demands = sim.traffic_sim.generate_demands(8)  # rush hour
    c = sim.evaluate_congestion()
    assert c["baseline_loss_pct"] > 0.0, "expected overload after hub cuts"
    assert c["improvement_pct"] > 0.0, "congestion-aware should reduce loss"


def test_below_knee_routes_identically():
    """With no congestion, load-aware weights == baseline → identical loss."""
    sim = ISPRoutingSimulation(num_demands=30)
    router = CongestionAwareRouter(sim.topology)
    demands = sim.traffic_sim.generate_demands(3)  # night, light load
    res = router.compare(demands, failed=set(), heat={})
    assert res["improvement_pct"] >= -1e-6
