import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core', 'python'))


from routing.topology import BackboneTopology
from routing.traffic import TrafficDemandSimulator

def test_pareto_traffic_distribution():
    topo = BackboneTopology()
    sim = TrafficDemandSimulator(topo.cities, num_demands=200, shape=1.5, scale_gbps=10.0)
    
    demands = sim.generate_demands(12)
    assert len(demands) == 200
    
    # Verify the Pareto 80/20 rule roughly holds:
    # Sort volumes in descending order
    volumes = sorted([d["volume_gbps"] for d in demands], reverse=True)
    total_vol = sum(volumes)
    
    # Sum top 20% of volumes
    top_20_count = len(volumes) // 5
    top_20_vol = sum(volumes[:top_20_count])
    
    # In a Pareto sample of shape 1.5, the top 20% should contain a large majority of total traffic volume (> 50%)
    assert top_20_vol > 0.5 * total_vol
    
    # Verify time multiplier: rush hour vs off-peak
    rush_demands = sim.generate_demands(8)  # 8 AM rush hour
    night_demands = sim.generate_demands(2)  # 2 AM night
    
    avg_rush = sum(d["volume_gbps"] for d in rush_demands) / len(rush_demands)
    avg_night = sum(d["volume_gbps"] for d in night_demands) / len(night_demands)
    
    # Rush hour traffic should be roughly 4x night traffic (rush hour multiplier=2.0, night=0.5)
    assert avg_rush > avg_night * 2.0
