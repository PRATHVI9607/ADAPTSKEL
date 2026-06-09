import math
import random
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple
import networkx as nx

@dataclass
class City:
    id: int
    name: str
    lat: float
    lon: float
    population: int

@dataclass
class Link:
    u: int
    v: int
    latency_ms: float
    capacity_gbps: float
    status: str = "healthy"  # "healthy" | "failed"

# 34 major Indian cities with lat/lon coordinates and populations
CITIES_DATA = [
    ("Delhi", 28.6139, 77.2090, 16787941),
    ("Mumbai", 19.0760, 72.8777, 12442373),
    ("Bangalore", 12.9716, 77.5946, 8443675),
    ("Chennai", 13.0827, 80.2707, 7088000),
    ("Kolkata", 22.5726, 88.3639, 4496694),
    ("Hyderabad", 17.3850, 78.4867, 6731790),
    ("Pune", 18.5204, 73.8567, 3124458),
    ("Ahmedabad", 23.0225, 72.5714, 5577940),
    ("Jaipur", 26.9124, 75.7873, 3046163),
    ("Lucknow", 26.8467, 80.9462, 2817105),
    ("Chandigarh", 30.7333, 76.7794, 1055450),
    ("Indore", 22.7196, 75.8577, 1964086),
    ("Coimbatore", 11.0168, 76.9558, 1601538),
    ("Kochi", 9.9312, 76.2673, 602046),
    ("Visakhapatnam", 17.6868, 83.2185, 2035354),
    ("Nagpur", 21.1458, 79.0882, 2405665),
    ("Surat", 21.1702, 72.8311, 4467797),
    ("Vadodara", 22.3072, 73.1812, 1670806),
    ("Bhopal", 23.2599, 77.4126, 1798218),
    ("Patna", 25.5941, 85.1376, 1684222),
    ("Guwahati", 26.1445, 91.7362, 957352),
    ("Thiruvananthapuram", 8.5241, 76.9366, 957730),
    ("Ranchi", 23.3441, 85.3096, 1073440),
    ("Raipur", 21.2514, 81.6296, 1010087),
    ("Bhubaneswar", 20.2961, 85.8245, 837737),
    ("Ludhiana", 30.9010, 75.8573, 1618879),
    ("Amritsar", 31.6340, 74.8723, 1132383),
    ("Agra", 27.1767, 78.0081, 1585704),
    ("Varanasi", 25.3176, 82.9739, 1198491),
    ("Madurai", 9.9252, 78.1198, 1017865),
    ("Vijayawada", 16.5062, 80.6480, 1034358),
    ("Jodhpur", 26.2389, 73.0243, 1033918),
    ("Srinagar", 34.0837, 74.7973, 1180570),
    ("Shimla", 31.1048, 77.1734, 169578)
]

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in kilometers."""
    R = 6371.0  # Earth's radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

class BackboneTopology:
    """Generates a realistic 34-city connected Indian ISP backbone network topology."""
    def __init__(self) -> None:
        self.cities: List[City] = []
        self.links: List[Link] = []
        
        # Build City objects
        for idx, (name, lat, lon, pop) in enumerate(CITIES_DATA):
            self.cities.append(City(id=idx, name=name, lat=lat, lon=lon, population=pop))
            
        self.city_to_id: Dict[str, int] = {c.name: c.id for c in self.cities}
        self.id_to_city: Dict[int, City] = {c.id: c for c in self.cities}
        
        self._generate_backbone()

    def _generate_backbone(self) -> None:
        """Create connected hub-and-spoke mesh topology."""
        g = nx.Graph()
        g.add_nodes_from(range(len(self.cities)))
        
        # 1. Designated Hubs
        hub_names = ["Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata", "Hyderabad"]
        hubs = [self.city_to_id[name] for name in hub_names]
        
        # 2. Inter-hub mesh connections
        hub_edges = [
            ("Delhi", "Mumbai"), ("Delhi", "Kolkata"), ("Delhi", "Hyderabad"),
            ("Delhi", "Jaipur"), ("Delhi", "Lucknow"),
            ("Mumbai", "Hyderabad"), ("Mumbai", "Bangalore"), ("Mumbai", "Pune"),
            ("Mumbai", "Ahmedabad"), ("Mumbai", "Surat"),
            ("Bangalore", "Chennai"), ("Bangalore", "Hyderabad"), ("Bangalore", "Kochi"),
            ("Chennai", "Hyderabad"), ("Chennai", "Kolkata"), ("Chennai", "Visakhapatnam"),
            ("Kolkata", "Hyderabad"), ("Kolkata", "Patna"), ("Kolkata", "Bhubaneswar"),
            ("Kolkata", "Guwahati"), ("Hyderabad", "Pune"), ("Hyderabad", "Nagpur"),
            ("Hyderabad", "Visakhapatnam")
        ]
        
        for u_name, v_name in hub_edges:
            if u_name in self.city_to_id and v_name in self.city_to_id:
                u, v = self.city_to_id[u_name], self.city_to_id[v_name]
                g.add_edge(u, v)

        # 3. Connect every non-hub city to its nearest hub
        for city in self.cities:
            if city.id in hubs:
                continue
            # Find nearest hub
            nearest_hub = min(hubs, key=lambda h_id: haversine_distance(
                city.lat, city.lon, self.id_to_city[h_id].lat, self.id_to_city[h_id].lon
            ))
            g.add_edge(city.id, nearest_hub)
            
        # 4. Add additional short-range mesh connectivity (dist < 450 km) with probability 0.30
        random.seed(42)  # For deterministic topology generation
        for i in range(len(self.cities)):
            for j in range(i + 1, len(self.cities)):
                if g.has_edge(i, j):
                    continue
                dist = haversine_distance(self.cities[i].lat, self.cities[i].lon, self.cities[j].lat, self.cities[j].lon)
                if dist < 450 and random.random() < 0.30:
                    g.add_edge(i, j)

        # Ensure the topology is fully connected, fallback to direct connections to Delhi if not
        if not nx.is_connected(g):
            components = list(nx.connected_components(g))
            main_comp = max(components, key=len)
            for comp in components:
                if comp == main_comp:
                    continue
                node_in_comp = list(comp)[0]
                g.add_edge(node_in_comp, 0)  # Connect to Delhi hub

        # Build Links list
        for u, v in g.edges():
            dist = haversine_distance(self.cities[u].lat, self.cities[u].lon, self.cities[v].lat, self.cities[v].lon)
            # Latency: 1 ms per 100 km
            latency = max(1.0, round((dist / 100.0) * 1.0, 1))
            
            # Hub connections get higher capacities
            is_high_capacity = u in hubs and v in hubs
            capacity = 100.0 if is_high_capacity else 40.0  # 100Gbps or 40Gbps
            self.links.append(Link(u=u, v=v, latency_ms=latency, capacity_gbps=capacity))
