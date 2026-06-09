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

# 50 major US cities with lat/lon coordinates and populations
CITIES_DATA = [
    ("New York", 40.7128, -74.0060, 8336817),
    ("Los Angeles", 34.0522, -118.2437, 3971883),
    ("Chicago", 41.8781, -87.6298, 2695598),
    ("Houston", 29.7604, -95.3698, 2320268),
    ("Phoenix", 33.4484, -112.0740, 1680992),
    ("Philadelphia", 39.9526, -75.1652, 1584064),
    ("San Antonio", 29.4241, -98.4936, 1547253),
    ("San Diego", 32.7157, -117.1611, 1423851),
    ("Dallas", 32.7767, -96.7970, 1343573),
    ("San Jose", 37.3382, -121.8863, 1021795),
    ("Austin", 30.2672, -97.7431, 978908),
    ("Jacksonville", 30.3322, -81.6557, 911507),
    ("Fort Worth", 32.7555, -97.3308, 909585),
    ("Columbus", 39.9612, -82.9988, 898553),
    ("Charlotte", 35.2271, -80.8431, 885705),
    ("San Francisco", 37.7749, -122.4194, 881549),
    ("Indianapolis", 39.7684, -86.1581, 876384),
    ("Seattle", 47.6062, -122.3321, 753675),
    ("Denver", 39.7392, -104.9903, 727211),
    ("Washington DC", 38.9072, -77.0369, 705749),
    ("Boston", 42.3601, -71.0589, 692600),
    ("El Paso", 31.7619, -106.4850, 681728),
    ("Nashville", 36.1627, -86.7816, 670820),
    ("Detroit", 42.3314, -83.0458, 670031),
    ("Oklahoma City", 35.4676, -97.5164, 655057),
    ("Portland", 45.5152, -122.6784, 654741),
    ("Las Vegas", 36.1716, -115.1398, 651319),
    ("Memphis", 35.1495, -90.0490, 651073),
    ("Louisville", 38.2527, -85.7585, 617638),
    ("Baltimore", 39.2904, -76.6122, 593490),
    ("Milwaukee", 43.0389, -87.9065, 590157),
    ("Albuquerque", 35.0844, -106.6511, 560513),
    ("Tucson", 32.2226, -110.9747, 548073),
    ("Fresno", 36.7378, -119.7871, 530074),
    ("Sacramento", 38.5816, -121.4944, 513624),
    ("Kansas City", 39.0997, -94.5786, 508090),
    ("Mesa", 33.4152, -111.8315, 508958),
    ("Atlanta", 33.7490, -84.3880, 506811),
    ("Omaha", 41.2565, -95.9345, 478192),
    ("Colorado Springs", 38.8339, -104.8214, 478221),
    ("Raleigh", 35.7796, -78.6382, 474069),
    ("Miami", 25.7617, -80.1918, 467963),
    ("Virginia Beach", 36.8529, -75.9780, 449974),
    ("Minneapolis", 44.9778, -93.2650, 429606),
    ("Oakland", 37.8044, -122.2712, 425195),
    ("Tulsa", 36.1540, -95.9928, 401352),
    ("Wichita", 37.6872, -97.3301, 389938),
    ("New Orleans", 29.9511, -90.0715, 383997),
    ("Arlington", 32.7357, -97.1081, 398854),
    ("Cleveland", 41.4993, -81.6944, 381009)
]

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in miles."""
    R = 3959.0  # Earth's radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

class BackboneTopology:
    """Generates a realistic 50-city connected ISP backbone network topology."""
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
        g.add_nodes_from(range(50))
        
        # 1. Designated Hubs
        hub_names = ["New York", "Chicago", "Atlanta", "Dallas", "Denver", "Los Angeles", "Seattle", "San Francisco", "Miami"]
        hubs = [self.city_to_id[name] for name in hub_names]
        
        # 2. Inter-hub mesh connections
        hub_edges = [
            ("New York", "Chicago"), ("New York", "Washington DC"), ("New York", "Boston"),
            ("New York", "Atlanta"), ("Chicago", "Denver"), ("Chicago", "Detroit"),
            ("Chicago", "Minneapolis"), ("Chicago", "Cleveland"), ("Atlanta", "Miami"),
            ("Atlanta", "Dallas"), ("Atlanta", "Washington DC"), ("Dallas", "Houston"),
            ("Dallas", "Denver"), ("Dallas", "Phoenix"), ("Denver", "Salt Lake City"),
            ("Denver", "Las Vegas"), ("Denver", "Kansas City"), ("Los Angeles", "San Francisco"),
            ("Los Angeles", "Phoenix"), ("Los Angeles", "San Diego"), ("Los Angeles", "Salt Lake City"),
            ("San Francisco", "Seattle"), ("San Francisco", "Portland"), ("San Francisco", "Salt Lake City"),
            ("Seattle", "Portland"), ("Seattle", "Minneapolis"), ("Miami", "Houston"), ("Washington DC", "Charlotte")
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
            
        # 4. Add additional short-range mesh connectivity (dist < 400 miles) with probability 0.25
        random.seed(42)  # For deterministic topology generation
        for i in range(50):
            for j in range(i + 1, 50):
                if g.has_edge(i, j):
                    continue
                dist = haversine_distance(self.cities[i].lat, self.cities[i].lon, self.cities[j].lat, self.cities[j].lon)
                if dist < 400 and random.random() < 0.25:
                    g.add_edge(i, j)

        # Ensure the topology is fully connected, fallback to direct connections to New York if not
        if not nx.is_connected(g):
            components = list(nx.connected_components(g))
            main_comp = max(components, key=len)
            for comp in components:
                if comp == main_comp:
                    continue
                node_in_comp = list(comp)[0]
                g.add_edge(node_in_comp, 0)  # Connect to NYC hub

        # Build Links list
        for u, v in g.edges():
            dist = haversine_distance(self.cities[u].lat, self.cities[u].lon, self.cities[v].lat, self.cities[v].lon)
            latency = max(1.0, round((dist / 100.0) * 1.0, 1))  # 1ms per 100 miles
            # NYC, Chicago, LA hub connections get higher capacities
            is_high_capacity = u in hubs and v in hubs
            capacity = 100.0 if is_high_capacity else 40.0  # 100Gbps or 40Gbps
            self.links.append(Link(u=u, v=v, latency_ms=latency, capacity_gbps=capacity))
