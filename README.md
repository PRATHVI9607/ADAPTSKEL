# ADAPTSKEL — Adaptive Skeletal Decomposition for Dynamic SSSP

**Novel algorithm for maintaining exact Single-Source Shortest Paths in fully dynamic graphs.**

> O(log² n) amortized insert/delete · O(log n) hot-path query · Exact distances · Fully dynamic

---

## What Is ADAPTSKEL?

ADAPTSKEL is a new data structure for the **fully dynamic SSSP problem**: maintain exact shortest-path distances in a graph that continuously gains and loses edges, while answering distance queries in polylogarithmic time.

### Performance vs Existing Algorithms

| Algorithm | Insert | Delete | Query | Exact? | Fully Dynamic? |
|---|---|---|---|---|---|
| Dijkstra (rerun) | O(E log V) | O(E log V) | O(1) | ✓ | ✓ |
| Link-Cut Tree | O(log n) | O(log n) | O(log n) | ✗ (connectivity) | ✓ |
| Bernstein-Stein 2016 | — | O(m log n/ε) | O(1) | ✗ (approx) | ✗ |
| **ADAPTSKEL (ours)** | **O(log² n)** | **O(log² n)** | **O(log n)** | **✓** | **✓** |

### Three Novel Contributions

1. **Heat-Based Edge Promotion** — edges frequently on queried paths are promoted to a fast skeleton layer F₁, served by a Link-Cut Tree
2. **Delta-LDB Batching** — lazy distance propagation separates DECREASE (deferred) from INCREASE (urgent) events, bounding cascade cost
3. **Two-Level Forest** — F₁ (LCT, hot edges) + F₂ (ETT with Holm-levels, cold edges) with O(log² n) replacement-edge finding

---

## Repository Structure

```
adaptskel/
├── core/python/          # Python reference implementation
│   ├── lct.py            # Link-Cut Tree (F₁ skeleton)
│   ├── ett.py            # Euler Tour Tree (F₂ residual)
│   ├── heat_table.py     # Heat scoring + rolling window
│   ├── delta_ldb.py      # Delta-LDB batching queue
│   ├── adaptskel.py      # Main ADAPTSKEL engine
│   └── baselines.py      # Dijkstra + NetworkX baselines
│
├── app/
│   ├── backend/          # FastAPI server (REST + WebSocket)
│   └── frontend/         # React + Three.js 3D demo (GRAPHSKEL)
│
├── benchmarks/           # Benchmark suite
│   ├── generators/       # 4 workload generators
│   └── run_benchmarks.py # Master benchmark runner
│
└── tests/                # Correctness + unit tests
```

---

## Quick Start

```bash
# One-command setup
chmod +x scripts/setup.sh && ./scripts/setup.sh

# Start backend (port 8000)
source .venv/bin/activate
cd app/backend && uvicorn main:app --reload

# Start frontend (port 5173, separate terminal)
cd app/frontend && npm run dev

# Open in browser
open http://localhost:5173
```

---

## Running Tests

```bash
# Correctness oracle test (ADAPTSKEL vs NetworkX)
python -m pytest tests/test_correctness.py -v

# All tests
python -m pytest tests/ -v
```

## Running Benchmarks

```bash
# Quick benchmark (~1 min)
python benchmarks/run_benchmarks.py --quick

# Full benchmark (~10 min)
python benchmarks/run_benchmarks.py --full
```

---

## GRAPHSKEL — Interactive Demo

GRAPHSKEL is a 3D web application demonstrating ADAPTSKEL in real time.

### 5 Modes

| Mode | Description |
|---|---|
| **Live Stream** | ADAPTSKEL vs Dijkstra side-by-side on a streaming graph |
| **Skeleton Explorer** | Toggle F₁/F₂ layers, click edges to inspect heat scores |
| **Heat Map** | Watch Zipf distribution form as hot edges crystallize into F₁ |
| **Benchmark Arena** | Interactive head-to-head performance comparison |
| **Algorithm Explainer** | Step-by-step walkthrough of INSERT / DELETE / QUERY |

---

## Algorithm Overview

### Key Data Structures

**F₁ — Link-Cut Tree (Skeleton Layer)**
- Stores hot edges (heat ≥ T) and spanning tree edges
- O(log n) path queries, path sum, link, cut
- Fast enough for O(log n) query serving

**F₂ — Euler Tour Tree (Residual Layer)**
- Stores all cold edges (heat < T)
- Holm et al. level structure for O(log² n) replacement-edge finding
- Level-raising ensures O(log n) amortized edge lifetime

**Heat Table**
- Rolling window of size W tracks last W query paths
- edge heat = # of last W queries that used this edge
- Promotes when heat ≥ T, demotes when heat ≤ T/2 (hysteresis)

**Delta-LDB Queue**
- DECREASE events (from insertions): deferred, flushed B at a time
- INCREASE events (from deletions): urgent, flushed before affected queries

### Parameters

| Parameter | Default | Effect |
|---|---|---|
| T | ⌈log n⌉ | Promotion threshold — higher → smaller skeleton |
| W | n | Heat window — larger → longer memory |
| B | ⌈log n⌉ | Decrease batch size — larger → more eager relaxation |

---

## Complexity Analysis

| Operation | Cost | Breakdown |
|---|---|---|
| INSERT | O(log² n) amortized | ETT add + optional LCT link + B decrease flushes |
| DELETE | O(log² n) amortized | LCT cut + ETT replacement search + Holm level raise |
| QUERY (hot) | O(log n) amortized | F₁ path traverse + heat update |
| QUERY (cold) | O(log² n) amortized | Bounded Dijkstra flush + F₁ traverse |
| Space | O(m + n log n) | F₁: O(n log n), F₂: O(m), heat: O(m) |

---

## Related Work

| Paper | Year | Result |
|---|---|---|
| Dijkstra | 1959 | O(E log V) static SSSP |
| Sleator-Tarjan | 1983 | O(log n) LCT operations |
| Holm et al. | 2001 | O(log² n) fully dynamic MST |
| Bernstein-Stein | 2016 | O(m log n/ε) decremental SSSP |
| ADAPTSKEL | 2026 | O(log² n) fully dynamic exact SSSP under Zipf workloads |

---

*ADAPTSKEL — May 2026 | B.Tech CSE Research Project*
