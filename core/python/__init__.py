"""
ADAPTSKEL Python reference implementation.

Public API
----------
AdaptSkel       — the main dynamic SSSP engine
DijkstraBaseline — naive recompute baseline for benchmarking / correctness checks
"""

try:
    from .adaptskel import AdaptSkel
    from .baselines import DijkstraBaseline
except ImportError:
    from adaptskel import AdaptSkel          # type: ignore[no-redef]
    from baselines import DijkstraBaseline   # type: ignore[no-redef]

__all__ = ["AdaptSkel", "DijkstraBaseline"]
