import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core', 'python'))


from routing.failures import LinkFailureSimulator

def test_failures_and_recoveries():
    links = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
    sim = LinkFailureSimulator(links, mtbf_hours=100.0, mean_recovery_min=5.0)
    
    # Initially no failed links
    assert len(sim.failed_links) == 0
    
    # Get next event delay
    delay, event_type, link = sim.get_next_event_delay(0.0)
    assert delay > 0.0
    assert event_type == "failure"
    assert link in links
    
    # Record failure
    recovery_time = sim.record_failure(link, 0.0)
    assert recovery_time > 0.0
    assert len(sim.failed_links) == 1
    
    # Next event delay (should check recovery time)
    delay2, event2, link2 = sim.get_next_event_delay(0.0)
    assert event2 in ["failure", "recovery"]
    
    # Record recovery
    sim.record_recovery(link)
    assert len(sim.failed_links) == 0
