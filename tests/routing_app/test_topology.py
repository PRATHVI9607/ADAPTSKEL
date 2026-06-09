import sys
import os
import networkx as nx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core', 'python'))


from routing.topology import BackboneTopology, haversine_distance

def test_haversine():
    # NYC to LA should be roughly 2440-2450 miles
    dist = haversine_distance(40.7128, -74.0060, 34.0522, -118.2437)
    assert 2400.0 < dist < 2500.0

def test_topology_nodes_and_connectivity():
    topo = BackboneTopology()
    assert len(topo.cities) == 50
    assert len(topo.links) > 0
    
    # Verify unique links
    edges = set((min(l.u, l.v), max(l.u, l.v)) for l in topo.links)
    assert len(edges) == len(topo.links)
    
    # Verify connectivity
    g = nx.Graph()
    g.add_nodes_from(range(50))
    for link in topo.links:
        g.add_edge(link.u, link.v)
        
    assert nx.is_connected(g)
    
    # Check degree bounds (should be relatively sparse mesh)
    avg_deg = sum(dict(g.degree()).values()) / 50.0
    assert 2.0 < avg_deg < 10.0
