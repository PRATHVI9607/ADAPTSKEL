import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core', 'python'))


from routing.simulation import ISPRoutingSimulation

def test_simulation_slos():
    sim = ISPRoutingSimulation(num_demands=20)
    
    # Run a few steps of the simulation
    for _ in range(5):
        step_res = sim.step()
        assert "sim_time" in step_res
        assert "event" in step_res
        assert "convergence_time_ms" in step_res
        assert "traffic_loss_pct" in step_res
        assert "path_optimality_pct" in step_res

    # Check metrics report
    report = sim.metrics.report()
    assert "avg_convergence_ms" in report
    assert "avg_traffic_loss_pct" in report
    assert "avg_path_optimality_pct" in report
    assert "availability_pct" in report
    
    # Confirm SLO metrics have valid values
    assert report["avg_convergence_ms"] >= 0.0
    assert 0.0 <= report["avg_traffic_loss_pct"] <= 100.0
    assert 0.0 <= report["avg_path_optimality_pct"] <= 100.0
    assert report["availability_pct"] >= 99.0

def test_query_throughput():
    # Verify throughput SLO (>= 100 QPS)
    sim = ISPRoutingSimulation(num_demands=1)
    
    t0 = time.perf_counter()
    num_queries = 200
    for _ in range(num_queries):
        sim.route_engine.route(0, 49)
        
    duration = time.perf_counter() - t0
    qps = num_queries / duration
    assert qps >= 100.0, f"Query throughput of {qps:.1f} QPS is below the 100 QPS threshold."
