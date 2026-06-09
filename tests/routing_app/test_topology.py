import sys
import os
import networkx as nx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core', 'python'))


from routing.topology import BackboneTopology, haversine_distance

def test_haversine():
    # Delhi to Mumbai should be roughly 1150-1200 km
    dist = haversine_distance(28.6139, 77.2090, 19.0760, 72.8777)
    assert 1100.0 < dist < 1250.0

def test_topology_nodes_and_connectivity():
    topo = BackboneTopology()
    assert len(topo.cities) == 34
    assert len(topo.links) > 0
    
    # Verify unique links
    edges = set((min(l.u, l.v), max(l.u, l.v)) for l in topo.links)
    assert len(edges) == len(topo.links)
    
    # Verify connectivity
    g = nx.Graph()
    g.add_nodes_from(range(34))
    for link in topo.links:
        g.add_edge(link.u, link.v)
        
    assert nx.is_connected(g)
    
    # Check degree bounds (should be relatively sparse mesh)
    avg_deg = sum(dict(g.degree()).values()) / 34.0
    assert 2.0 < avg_deg < 10.0
