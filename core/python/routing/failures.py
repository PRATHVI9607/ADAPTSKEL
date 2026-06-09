import random
import math
from typing import List, Tuple, Dict, Set

class LinkFailureSimulator:
    """Simulates link failures based on a Poisson process and recoveries on an exponential distribution."""
    def __init__(self, links_keys: List[Tuple[int, int]], mtbf_hours: float = 100000.0, mean_recovery_min: float = 5.0) -> None:
        self.links = links_keys  # List of (u, v) tuples
        self.mtbf_hours = mtbf_hours
        self.mean_recovery_seconds = mean_recovery_min * 60.0
        
        # Overall failure rate for the network (lambda) per second
        # MTBF hours to seconds: mtbf_hours * 3600
        # Failure rate of 1 link: 1 / (MTBF * 3600)
        # Total network failure rate: len(links) * (1 / (MTBF * 3600))
        self.single_link_failure_rate = 1.0 / (self.mtbf_hours * 3600.0)
        self.network_failure_rate = len(self.links) * self.single_link_failure_rate
        
        self.failed_links: Dict[Tuple[int, int], float] = {}  # (u, v) -> recovery_sim_time

    def get_next_event_delay(self, current_sim_time: float, active_failures_limit: int = 5) -> Tuple[float, str, Tuple[int, int]]:
        """
        Calculate the simulated time delay to the next event and returns (delay_seconds, event_type, link_key).
        Events are either a new failure (Poisson process) or a recovery (exponential delay).
        """
        # 1. Time to next network failure (exponential distribution)
        # Avoid dividing by zero if network_failure_rate is extremely small or zero
        time_to_failure = random.expovariate(self.network_failure_rate) if self.network_failure_rate > 0 else float('inf')
        
        # If we have reached the failures limit, we can't fail more links
        if len(self.failed_links) >= active_failures_limit:
            time_to_failure = float('inf')

        # 2. Time to next recovery
        time_to_recovery = float('inf')
        next_recovery_link = None
        
        for link, recovery_time in self.failed_links.items():
            time_left = recovery_time - current_sim_time
            if time_left < time_to_recovery:
                time_to_recovery = max(0.0, time_left)
                next_recovery_link = link

        # Determine which event happens first
        if time_to_failure < time_to_recovery:
            # A failure occurs
            # Choose which healthy link fails
            healthy_links = [l for l in self.links if l not in self.failed_links]
            if not healthy_links:
                return time_to_recovery, "recovery", next_recovery_link  # type: ignore[return-value]
            failed_link = random.choice(healthy_links)
            return time_to_failure, "failure", failed_link
        else:
            # A recovery occurs
            return time_to_recovery, "recovery", next_recovery_link  # type: ignore[return-value]

    def record_failure(self, link: Tuple[int, int], current_sim_time: float) -> float:
        """Mark a link as failed and generate its recovery timestamp. Returns recovery time."""
        recovery_duration = random.expovariate(1.0 / self.mean_recovery_seconds)
        recovery_time = current_sim_time + recovery_duration
        self.failed_links[link] = recovery_time
        return recovery_duration

    def record_recovery(self, link: Tuple[int, int]) -> None:
        """Mark a link as recovered."""
        self.failed_links.pop(link, None)
