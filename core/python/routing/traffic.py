import random
from typing import List, Dict, Any, Optional, Tuple
from .topology import City, haversine_distance

class TrafficDemandSimulator:
    """Generates realistic traffic demands between cities following a Pareto distribution."""
    def __init__(
        self,
        cities: List[City],
        num_demands: int = 100,
        shape: float = 1.5,
        scale_gbps: float = 10.0,
        max_volume_gbps: Optional[float] = None,
    ) -> None:
        self.cities = cities
        self.num_demands = num_demands
        self.shape = shape
        self.scale_gbps = scale_gbps
        # Optional ceiling on a single demand's volume. Pareto is heavy-tailed
        # by design (that's the point — a few flows dominate traffic), but
        # without any ceiling a handful of draws per batch land at 10-20x the
        # mean and can exceed every link's real capacity regardless of
        # network health. Left as None here so this generator's own
        # statistical shape is testable in isolation; callers that know the
        # real backbone's link capacities (see ISPRoutingSimulation) should
        # pass a ceiling derived from that topology.
        self.max_volume_gbps = max_volume_gbps

        self.city_ids = [c.id for c in cities]
        self.populations = [c.population for c in cities]

    def _distance_weight(self, c1: City, c2: City) -> float:
        """Weight destination probability by distance (prefer long-haul routes)."""
        dist = haversine_distance(c1.lat, c1.lon, c2.lat, c2.lon)
        return 1.0 + (dist / 1000.0)  # Linear boost for distance

    def generate_demands(self, time_of_day_hours: int = 12) -> List[Dict[str, Any]]:
        """Generate demands using population/distance weights and Pareto-distributed volume."""
        demands = []

        # Time-of-day multipliers: rush hour (7-9am, 5-7pm) = 2.0x, night (11pm-5am) = 0.5x, else 1.0x
        if time_of_day_hours in [7, 8, 17, 18]:
            multiplier = 2.0
        elif time_of_day_hours in [23, 0, 1, 2, 3, 4]:
            multiplier = 0.5
        else:
            multiplier = 1.0

        for _ in range(self.num_demands):
            # Select source city weighted by population
            src_id = random.choices(self.city_ids, weights=self.populations)[0]
            src_city = next(c for c in self.cities if c.id == src_id)

            # Select destination city weighted by population and distance
            dest_options = [c for c in self.cities if c.id != src_id]
            dest_weights = [
                c.population * self._distance_weight(src_city, c)
                for c in dest_options
            ]

            dest_city = random.choices(dest_options, weights=dest_weights)[0]

            # Pareto-distributed traffic volume: x = scale * (1 - u)^(-1/shape)
            u = random.random()
            # Avoid u = 1.0 to prevent division by zero / overflow
            u = min(0.9999, u)
            raw_volume = self.scale_gbps * (1.0 - u) ** (-1.0 / self.shape)
            volume = raw_volume * multiplier
            if self.max_volume_gbps is not None:
                volume = min(volume, self.max_volume_gbps)
            volume = round(volume, 2)

            demands.append({
                "source": src_id,
                "destination": dest_city.id,
                "volume_gbps": volume
            })

        return demands
