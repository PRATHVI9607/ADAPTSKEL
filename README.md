# ADAPTSKEL — Adaptive Skeletal Decomposition for Dynamic SSSP

**Novel algorithm for maintaining exact Single-Source Shortest Paths in fully dynamic graphs.**

> O(log² n) amortized insert/delete · O(log n) hot-path query · Exact distances · Fully dynamic

---

## What Is ADAPTSKEL?

ADAPTSKEL is a data structure for the **dynamic SSSP problem**: maintaining exact shortest-path distances from a fixed source in a graph that continuously gains, loses, and reweights edges, while answering source-rooted distance queries in O(1).

### What ADAPTSKEL actually delivers (honest claims)

| Operation | Cost | Notes |
|---|---|---|
| `query(source, t)` | **O(1)** | direct read of an incrementally-maintained label — no oracle, no recompute |
| `query(s, t)`, s ≠ source | O(E log V) | one Dijkstra from s; the structure only accelerates the fixed source |
| `insert` / edge-decrease | output-sensitive | Dijkstra relaxation touching only vertices whose label improves |
| `delete` / edge-increase | output-sensitive | Ramalingam–Reps: only the *affected* subtree is recomputed |

Every update is **exact** (validated against a NetworkX oracle every mutation, in debug mode and in `tests/test_correctness.py`). Incremental updates beat a full Dijkstra rerun when changes are **local** (the common case) and degrade to a single Dijkstra in the worst case.

> **Intellectual-honesty note (please read before presenting):** exact fully-dynamic SSSP with polylog **worst-case** update *and* query is not known to exist and is conditionally impossible under the OMv conjecture. ADAPTSKEL does **not** claim that. Its contribution is the O(1) source-rooted query backed by output-sensitive incremental maintenance, plus the heat-driven F₁/F₂ skeleton used for visualisation and congestion signalling. NetworkX appears only as a test oracle, never on the answer path.

### Three Novel Contributions

1. **Heat-Based Edge Promotion** — edges frequently on queried paths are promoted to a fast skeleton layer F₁, served by a Link-Cut Tree
2. **Delta-LDB Batching** — lazy distance propagation separates DECREASE (deferred) from INCREASE (urgent) events, bounding cascade cost
3. **Two-Level Forest** — F₁ (LCT, hot edges) + F₂ (ETT with Holm-levels, cold edges) with O(log² n) replacement-edge finding

---

## Repository Structure

```
adaptskel/
├── core/python/          # Python reference implementation of ADAPTSKEL
│   ├── lct.py            # Link-Cut Tree (F₁ skeleton)
│   ├── ett.py            # Euler Tour Tree (F₂ residual)
│   ├── heat_table.py     # Heat scoring + rolling window
│   ├── delta_ldb.py      # Delta-LDB batching queue
│   ├── adaptskel.py      # Main ADAPTSKEL engine
│   └── baselines.py      # Dijkstra + NetworkX baselines
│
├── app/
│   ├── backend/          # FastAPI server (REST + WebSocket)
│   ├── frontend/         # React + Three.js 3D demo (GRAPHSKEL)
│   └── routing-app/      # React + Leaflet.js dashboard (Network Routing App)
│
├── benchmarks/           # Benchmark suite
│   ├── generators/       # Workload generators
│   └── run_benchmarks.py # Master benchmark runner
│
└── tests/                # Core correctness & application tests
```

---

## Core Applications

### 1. GRAPHSKEL (3D Explainer & Benchmark Arena)
An interactive 3D web application displaying ADAPTSKEL vs Dijkstra side-by-side on a streaming graph, showing layer promotion, heat crystallization, and performance arenas.

### 2. Network Routing Application (ISP Backbone Simulation)
A real-time simulation of an ISP backbone routing system using a 34-city Indian topology (Tier-1 and Tier-2 hubs). Features Poisson-distributed link failures (realistic MTBF), Pareto-distributed traffic demands (80/20 rule), and live Leaflet-based routing pathfinders with latency calculations (1 ms per 100 km) and SLO validation.

**Congestion control (the "many flows down the same road" problem).** The plain router sends every demand down the *latency*-shortest path, so heavily-used hub links can overload even with no failures. The `CongestionAwareRouter` (`core/python/routing/congestion.py`) routes with **load-adaptive edge weights**: as a link approaches capacity its effective weight rises (a knee-hinge penalty), steering later flows onto alternate paths — a stream of dynamic edge-reweight events, exactly what ADAPTSKEL absorbs. ADAPTSKEL **heat** scores act as a "this link is popular" prior so the busiest-and-hottest links shed load first. The dashboard shows **latency-only vs congestion-aware** traffic loss side by side; below capacity the two are identical (congestion-aware is never worse), and under failure-driven overload it cuts loss substantially (e.g. 4 hub cuts: **71% → 27%** loss).

---

## Running with Docker Compose

We provide two pre-configured Docker environments which can run independently or concurrently:

### A. Comprehensive Edition (`prd1-comprehensive`)
Features strict Docker builds, full health check cycles, and PostgreSQL logging of routing metrics.
* **Backend API**: [http://localhost:8000](http://localhost:8000)
* **GRAPHSKEL 3D Demo**: [http://localhost:5173](http://localhost:5173)
* **Network Routing App**: [http://localhost:5175](http://localhost:5175)

To spin it up (from the `prd1-comprehensive` branch):
```bash
git checkout prd1-comprehensive
docker compose up --build -d
```

### B. Minimal Edition (`prd2-minimal`)
Optimized for developer builds with warning-only fallback logging if PostgreSQL is offline.
* **Backend API**: [http://localhost:8001](http://localhost:8001)
* **GRAPHSKEL 3D Demo**: [http://localhost:5174](http://localhost:5174)
* **Network Routing App**: [http://localhost:5176](http://localhost:5176)

To spin it up (from the `prd2-minimal` branch):
```bash
git checkout prd2-minimal
docker compose up --build -d
```

---

## Running Locally

To run the backend and frontends locally on your machine, follow these steps:

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ & npm

### 2. Backend Setup
Set up a virtual environment and install dependencies:
```bash
# From repository root
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install requirements
pip install -r app/backend/requirements.txt
pip install uvicorn gunicorn
```

Run the FastAPI backend server:
```bash
# Set PYTHONPATH to include the routing module
export PYTHONPATH=$PYTHONPATH:$(pwd) # On Windows PowerShell: $env:PYTHONPATH += ";$PWD"

# Start the server (default port 8000)
cd app/backend
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup — GRAPHSKEL (3D Demo)
```bash
cd app/frontend
npm install

# Run the dev server (defaults to port 5173)
npm run dev
```

### 4. Frontend Setup — Network Routing Application
```bash
cd app/routing-app
npm install

# Build and run the Leaflet dashboard (defaults to port 5174, maps to backend on port 8000)
VITE_API_BASE=http://localhost:8000 npm run dev
```

---

## Running Tests

We run our tests using `pytest`.

```bash
# Active virtual environment
pip install pytest pytest-asyncio pytest-cov anyio

# Run the core ADAPTSKEL algorithm unit & correctness tests
pytest tests/ -v

# Run the Network Routing Application simulation & SLO tests
pytest tests/routing_app/ -v
```

---

## Running Benchmarks

Evaluate ADAPTSKEL's performance against Dijkstra and NetworkX baselines under various workloads:

```bash
# Quick benchmark (~1 min)
python benchmarks/run_benchmarks.py --quick

# Full benchmark (~10 min)
python benchmarks/run_benchmarks.py --full
```

---

*ADAPTSKEL — June 2026 | Research Project*
