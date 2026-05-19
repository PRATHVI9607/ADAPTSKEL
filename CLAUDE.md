# ADAPTSKEL — CLAUDE.md
> Master instruction file for Claude Code. Read this entire file before doing anything.
> This file overrides all default Claude Code behavior for this project.

---

## 0. WHO YOU ARE IN THIS PROJECT

You are the lead engineer on **ADAPTSKEL** — a novel fully dynamic graph algorithm project built by a 4th-semester CSE student (Loki) for a college research demo. Your job is to:

1. Implement the ADAPTSKEL algorithm correctly in Python + C++
2. Build **GRAPHSKEL** — the 3D interactive demo application
3. Generate benchmark comparisons vs existing algorithms
4. Maintain code quality, correctness, and visual polish

The project has two audiences:
- **Academic (professor/examiner):** needs to see correctness proofs, complexity analysis, comparisons
- **Demo (anyone watching):** needs to be visually impressive, intuitive, and clearly show ADAPTSKEL winning

**Always optimize for both simultaneously.**

---

## 1. PROJECT OVERVIEW

### What ADAPTSKEL Is
A fully dynamic Single-Source Shortest Path (SSSP) algorithm that maintains exact distances in a graph being continuously modified (edge insertions + deletions) in O(log² n) amortized time per update and O(log n) for hot path queries.

### The Three Novel Contributions
1. **Heat-Based Edge Promotion** — edges that appear frequently on queried paths are promoted to a fast "skeleton" layer (F₁), making hot queries O(log n)
2. **Delta-LDB Batching** — lazy distance propagation that separates increase/decrease events, bounding cascade cost to O(log² n)
3. **Two-Level Forest (F₁ + F₂)** — Link-Cut Tree skeleton + Euler Tour Tree residual, with O(log n) replacement-edge finding on deletion

### What We're Beating
| Algorithm | Insert | Delete | Query | Exact? | Fully Dynamic? |
|---|---|---|---|---|---|
| Dijkstra (rerun) | O(E log V) | O(E log V) | O(1) | ✓ | ✓ |
| Link-Cut Tree | O(log n) | O(log n) | O(log n) | ✗ (connectivity) | ✓ |
| Bernstein-Stein | ✗ | O(m log n/ε) | O(1) | ✗ (approx) | ✗ |
| **ADAPTSKEL** | **O(log² n)** | **O(log² n)** | **O(log n)** | **✓** | **✓** |

---

## 2. REPOSITORY STRUCTURE

```
adaptskel/
├── CLAUDE.md                    ← you are here
├── PRD.md                       ← full product requirements (read this too)
├── README.md                    ← public-facing project readme
│
├── core/                        ← Algorithm implementation
│   ├── cpp/                     ← C++ core (performance-critical)
│   │   ├── lct.hpp              ← Link-Cut Tree (F₁ skeleton)
│   │   ├── lct.cpp
│   │   ├── ett.hpp              ← Euler Tour Tree (F₂ residual)
│   │   ├── ett.cpp
│   │   ├── adaptskel.hpp        ← Main engine interface
│   │   ├── adaptskel.cpp        ← INSERT / DELETE / QUERY logic
│   │   ├── heat_table.hpp       ← Heat score + rolling window
│   │   ├── delta_ldb.hpp        ← Delta-LDB batching queue
│   │   └── CMakeLists.txt
│   │
│   ├── python/                  ← Python implementation (for benchmarking + demo)
│   │   ├── adaptskel.py         ← Pure Python ADAPTSKEL (readable reference)
│   │   ├── lct.py               ← Link-Cut Tree in Python
│   │   ├── ett.py               ← Euler Tour Tree in Python
│   │   ├── heat_table.py        ← Heat scoring system
│   │   ├── delta_ldb.py         ← Delta-LDB queue
│   │   └── baselines.py         ← Dijkstra, BFS, networkx wrappers for comparison
│   │
│   └── bindings/                ← pybind11 C++→Python bridge
│       ├── bindings.cpp
│       └── CMakeLists.txt
│
├── benchmarks/                  ← All benchmarking code
│   ├── run_benchmarks.py        ← Master benchmark runner
│   ├── generators/
│   │   ├── random_graph.py      ← Erdos-Renyi, Barabasi-Albert generators
│   │   ├── road_network.py      ← Road network simulator
│   │   ├── zipf_workload.py     ← Zipf-distributed query workload generator
│   │   └── adversarial.py       ← Worst-case workload generator
│   ├── datasets/                ← Downloaded graph datasets (gitignored if large)
│   │   └── .gitkeep
│   └── results/                 ← Benchmark output JSON/CSV (auto-generated)
│       └── .gitkeep
│
├── app/                         ← GRAPHSKEL demo application
│   ├── frontend/                ← React + Three.js 3D visualization
│   │   ├── src/
│   │   │   ├── main.tsx
│   │   │   ├── App.tsx
│   │   │   ├── components/
│   │   │   │   ├── GraphCanvas3D.tsx    ← Three.js 3D graph renderer
│   │   │   │   ├── SkeletonOverlay.tsx  ← F₁/F₂ layer visualization
│   │   │   │   ├── BenchmarkPanel.tsx   ← Live timing comparison bars
│   │   │   │   ├── ControlPanel.tsx     ← Graph controls + presets
│   │   │   │   ├── QueryTracer.tsx      ← Animated shortest path tracer
│   │   │   │   ├── HeatMap.tsx          ← Edge heat score heatmap
│   │   │   │   └── StatsOverlay.tsx     ← Live algorithm stats HUD
│   │   │   ├── engine/
│   │   │   │   ├── AdaptSkelEngine.ts   ← TypeScript ADAPTSKEL port (for browser)
│   │   │   │   ├── DijkstraEngine.ts    ← Dijkstra for comparison
│   │   │   │   └── GraphState.ts        ← Shared graph state management
│   │   │   ├── shaders/
│   │   │   │   ├── edge.vert.glsl       ← Custom edge shader (heat color)
│   │   │   │   └── node.frag.glsl       ← Node glow shader
│   │   │   └── styles/
│   │   │       └── globals.css
│   │   ├── public/
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   └── tsconfig.json
│   │
│   └── backend/                 ← FastAPI server (bridges Python algo to frontend)
│       ├── main.py              ← FastAPI app entry point
│       ├── routers/
│       │   ├── graph.py         ← /insert /delete /query endpoints
│       │   └── benchmark.py     ← /benchmark/run /benchmark/results endpoints
│       ├── services/
│       │   ├── adaptskel_service.py  ← Wraps Python ADAPTSKEL engine
│       │   └── benchmark_service.py ← Runs comparative benchmarks
│       └── requirements.txt
│
├── docs/                        ← Documentation
│   ├── algorithm_explanation.md ← Plain-English explanation (for mam)
│   ├── proof_sketch.md          ← Formal amortized analysis
│   ├── api_reference.md         ← Backend API docs
│   └── slides/                  ← Presentation materials
│
├── tests/                       ← All tests
│   ├── test_correctness.py      ← ADAPTSKEL vs oracle (NetworkX)
│   ├── test_lct.py              ← Link-Cut Tree unit tests
│   ├── test_ett.py              ← Euler Tour Tree unit tests
│   ├── test_heat.py             ← Heat table unit tests
│   └── test_api.py              ← Backend API integration tests
│
├── scripts/                     ← Utility scripts
│   ├── setup.sh                 ← One-command project setup
│   ├── download_datasets.sh     ← Download benchmark graph datasets
│   └── generate_figures.py      ← Generate paper-quality benchmark figures
│
└── .github/
    └── workflows/
        └── ci.yml               ← GitHub Actions: test + benchmark on push
```

---

## 3. SKILLS TO USE — INSTALLATION + USAGE

This project uses Claude Skills for specialized tasks. Install them as follows:

### 3.1 frontend-design skill
**What:** Creates distinctive, production-grade frontend UI. Use for ALL UI work in `app/frontend/`.
**Location:** Already available at `/mnt/skills/public/frontend-design/SKILL.md`
**When to invoke:** ANY time you write React components, CSS, or UI layout code. Read it first.
```bash
# To access during Claude Code sessions:
cat /mnt/skills/public/frontend-design/SKILL.md
```
**Rules for this project:**
- 3D aesthetic using Three.js — nodes are glowing spheres, edges are luminous cylinders
- Color scheme: deep space black (#0a0a0f) background, electric blue (#00d4ff) skeleton edges, amber (#ff8c00) heat glow, ghost white (#f0f0ff) cold edges
- Font: `Space Grotesk` for UI chrome, `JetBrains Mono` for numbers/stats
- NO flat 2D graphs — everything in 3D with depth, perspective, and camera controls
- Glass morphism panels for control UI (backdrop-filter blur)
- Particle effects on edge insertions/deletions

### 3.2 algorithmic-art skill
**What:** Creates p5.js generative art and algorithmic visualizations.
**Location:** `/mnt/skills/examples/algorithmic-art/SKILL.md`
**When to invoke:** For the heat-map visualization, the Zipf distribution visualizer, and any generative visual in the demo.
```bash
cat /mnt/skills/examples/algorithmic-art/SKILL.md
```
**Use for:**
- Animated heat score particle system (edges glow as they heat up)
- Zipf distribution visualization on the benchmark panel
- Skeleton "crystallization" animation when edges promote to F₁

### 3.3 web-artifacts-builder skill
**What:** Builds multi-component React apps with Tailwind + shadcn/ui.
**Location:** `/mnt/skills/examples/web-artifacts-builder/SKILL.md`
**When to invoke:** When building complex interactive components in `app/frontend/src/components/`.
```bash
cat /mnt/skills/examples/web-artifacts-builder/SKILL.md
```

### 3.4 canvas-design skill
**What:** Creates poster-quality visual designs.
**Location:** `/mnt/skills/examples/canvas-design/SKILL.md`
**When to invoke:** For generating the project poster, presentation cover slide, and any static visual assets.
```bash
cat /mnt/skills/examples/canvas-design/SKILL.md
```

### 3.5 theme-factory skill
**What:** Applies consistent design themes across artifacts.
**Location:** `/mnt/skills/examples/theme-factory/SKILL.md`
**When to invoke:** When building the presentation slides or any multi-page document output.
```bash
cat /mnt/skills/examples/theme-factory/SKILL.md
```

### 3.6 mcp-builder skill
**What:** Builds MCP servers for external integrations.
**Location:** `/mnt/skills/examples/mcp-builder/SKILL.md`
**When to invoke:** If we need to connect GRAPHSKEL to external graph data sources (OSM, SNAP datasets).
```bash
cat /mnt/skills/examples/mcp-builder/SKILL.md
```

### Skill Usage Rule
> **MANDATORY:** Before writing any code in the domain of a skill listed above, `cat` the SKILL.md first. Never skip this. Skills contain environment-specific constraints that will save you from bugs.

---

## 4. TECH STACK

### Algorithm Core
```
Language:     Python 3.11+ (reference impl) + C++20 (performance impl)
Build:        CMake 3.25+, pybind11 for bindings
Key deps:     networkx (oracle/baseline), numpy, scipy
Testing:      pytest, hypothesis (property-based tests)
```

### Backend API
```
Framework:    FastAPI + uvicorn
WebSocket:    For live graph state streaming to frontend
Serialization: msgpack (fast) + JSON (debug)
Key deps:     fastapi, uvicorn, websockets, networkx, numpy
```

### Frontend / Demo App
```
Framework:    React 18 + TypeScript + Vite
3D Engine:    Three.js + @react-three/fiber + @react-three/drei
Graph layout: d3-force-3d (3D force-directed layout)
State:        Zustand
Styling:      Tailwind CSS + custom CSS variables
Charts:       Recharts (benchmark panels)
Animation:    Framer Motion (UI) + Three.js animations (3D)
Shaders:      GLSL via Three.js ShaderMaterial
```

### Benchmarking
```
Profiling:    cProfile, line_profiler, memory_profiler
Visualization: matplotlib, seaborn (paper figures)
Datasets:     networkx generators + SNAP datasets
```

---

## 5. THE DEMO APPLICATION — GRAPHSKEL

### What GRAPHSKEL Does
GRAPHSKEL is a real-time 3D interactive visualization that demonstrates ADAPTSKEL beating Dijkstra. It has five modes:

#### Mode 1: Live Streaming Graph
- A graph streams in — edges insert and delete in real time
- Two panels: left = ADAPTSKEL running, right = Dijkstra rerunning from scratch
- Both panels show the same graph but each algorithm's internal state
- A query runs every 2 seconds — watch ADAPTSKEL answer in microseconds while Dijkstra labors
- Live timing bars at the bottom show the gap growing as the graph scales

#### Mode 2: Skeleton Explorer
- Static graph loaded (presets: road network, social graph, random)
- Toggle F₁ (skeleton) vs F₂ (residual) layer visibility
- Click any edge to see its heat score, level, which forest it's in
- Run queries — watch the hot path pulse electric blue through F₁
- Manually insert/delete edges and watch the skeleton reshape in 3D

#### Mode 3: Heat Score Live Map
- Heatmap overlay on the 3D graph
- Edges color from cold ghost-white → warm amber → hot electric blue as heat builds
- Shows the power-law distribution forming in real time — a few edges get super hot
- Run the Zipf workload and watch F₁ crystallize around the high-traffic subgraph

#### Mode 4: Benchmark Arena
- Choose graph type (random, road, social, adversarial) and size (100 → 100,000 nodes)
- Click "Run Benchmark" — both algorithms run, timing captured
- Results shown as:
  - **3D bar chart** (Three.js): ADAPTSKEL vs Dijkstra latency bars floating in space
  - **Line chart** (Recharts): ops/second vs graph size
  - **Big number display**: "ADAPTSKEL is X× faster" with the X dynamically computed
- Export results as CSV or PNG

#### Mode 5: Algorithm Explainer
- Step-through animation of a single INSERT / DELETE / QUERY operation
- Each step highlights exactly what happens in the data structure
- Narrated with text callouts explaining the algorithm
- Designed for showing mam — "here's exactly what's happening"

### UI Layout
```
┌─────────────────────────────────────────────────────────┐
│  GRAPHSKEL          [Mode tabs]          [Settings] [?]  │  ← Header (glass)
├──────────┬──────────────────────────────────┬───────────┤
│          │                                  │           │
│ Control  │     3D Graph Canvas              │  Stats    │
│ Panel    │     (Three.js)                   │  HUD      │
│          │                                  │           │
│ - Preset │     [nodes glowing in 3D]        │ Ops/sec   │
│ - Speed  │     [edges pulsing]              │ Hot ratio │
│ - Size   │     [path traces]                │ F₁ edges  │
│ - Mode   │                                  │ Δ queue   │
│          │                                  │           │
├──────────┴──────────────────────────────────┴───────────┤
│  Benchmark: ADAPTSKEL ████████████████ 0.04ms           │  ← Bottom bar
│             Dijkstra  ██              1.82ms   45.5× faster │
└─────────────────────────────────────────────────────────┘
```

### 3D Visual Design Rules
- **Background:** Deep space (#0a0a0f) with subtle star particle field
- **Nodes:** Glowing spheres, size = degree centrality, color = component membership
- **F₁ edges (skeleton):** Electric blue (#00d4ff) cylinders, emissive glow, slightly thicker
- **F₂ edges (residual):** Ghost white (#9090a0) thin lines, low opacity
- **Hot path on query:** Bright gold (#ffd700) pulse animation traveling along path edges
- **Edge insertion:** Green particle burst at midpoint, edge materializes with scale animation
- **Edge deletion:** Red flash, edge shatters into particles and dissolves
- **Camera:** Orbit controls, auto-rotate slowly when idle, snap-to-fit on graph load
- **Lighting:** Point lights on active nodes, ambient fill, bloom post-processing

---

## 6. GRAPH GENERATION FOR BENCHMARKS

### Generator 1: Zipf Workload Generator
```python
# core: generate a graph + query sequence that proves ADAPTSKEL's advantage
# The key: queries follow Zipf distribution over paths
# 20% of edges will receive 80% of queries
# This is what makes ADAPTSKEL's skeleton crystallize and dominate

def generate_zipf_workload(n, m, num_queries, alpha=1.2):
    # Returns: (graph, operation_sequence)
    # operation_sequence = list of (INSERT/DELETE/QUERY, args)
    # Queries are Zipf-sampled from pre-computed "popular paths"
```

### Generator 2: Scaling Benchmark Generator
```python
# For each n in [100, 500, 1K, 5K, 10K, 50K, 100K]:
#   - Generate Barabasi-Albert graph (power-law degree, like real networks)
#   - Run 10K mixed operations (70% query, 20% insert, 10% delete)
#   - Measure: time per op for ADAPTSKEL vs Dijkstra
#   - Plot: ADAPTSKEL stays flat (polylog), Dijkstra grows linearly
```

### Generator 3: Adversarial Generator
```python
# Shows ADAPTSKEL's honest limitation
# Adversary always queries completely different paths = skeleton never forms
# Both algorithms degrade similarly
# This shows intellectual honesty — we're not hiding the weakness
```

### Generator 4: Road Network Simulator
```python
# Grid graph with added shortcuts (approximates road networks)
# Realistic edge weight distributions (travel times)
# Periodic "congestion events" = weight updates (DELETE + INSERT same edge, new weight)
# "Road closures" = DELETE only
# "New roads" = INSERT
```

### Key Benchmark: The Money Plot
The main figure that shows ADAPTSKEL winning:
- X-axis: graph size (log scale, 100 → 100K nodes)
- Y-axis: average query time (log scale, μs)
- Line 1 (blue): ADAPTSKEL — rises as O(log² n), nearly flat on log scale
- Line 2 (red): Dijkstra — rises as O(n log n), steep on log scale
- The gap at 100K nodes should be ~50×
- This is the figure you show mam

---

## 7. ALGORITHM IMPLEMENTATION RULES

### Correctness is Non-Negotiable
Before any performance work, the algorithm must be 100% correct.
Run correctness tests after EVERY change to `core/`:

```bash
python -m pytest tests/test_correctness.py -v
```

The correctness test runs ADAPTSKEL and NetworkX Dijkstra in parallel on identical operation sequences and asserts zero distance discrepancies. If any test fails, fix it before moving on. No exceptions.

### Python Implementation First
Write the Python implementation first (`core/python/adaptskel.py`). It must be:
- Clean and readable — this is the "reference" that the professor reads
- Heavily commented with complexity annotations on each method
- Docstrings explaining the algorithm idea, not just what the code does

```python
def insert(self, u: int, v: int, w: float) -> None:
    """
    Insert edge (u,v,w) into the dynamic graph.
    
    Algorithm:
    1. Add edge to F₂ (cold residual layer) — O(log n)
    2. If u and v are disconnected in F₁, promote edge to F₁ — O(log n)  
    3. Enqueue DECREASE event if edge improves distances — O(1)
    4. Flush up to B=O(log n) pending DECREASE events — O(B log n) = O(log² n)
    
    Amortized complexity: O(log² n)
    """
```

### C++ Implementation Second
Only after Python passes all correctness tests. The C++ version must produce bit-identical results to Python on all test cases.

### Never Break the Invariants
At all times, the following must hold:
1. `F₁ ∪ F₂ = E` (all edges in exactly one layer)
2. `F₁` is a valid spanning forest of G
3. `dist[v]` = exact shortest path distance from source to v
4. `heat[e]` ≤ W for all edges e (bounded by window)
5. All edges in F₁ have `heat[e] ≥ T/2` (hysteresis lower bound)

Add assertion checks for all five invariants in debug mode:
```python
def _assert_invariants(self):
    assert set(self.F1.edges()) | set(self.F2.edges()) == set(self.G.edges())
    # ... etc
```

---

## 8. RUNNING THE PROJECT

### Setup (one command)
```bash
chmod +x scripts/setup.sh && ./scripts/setup.sh
```

This script:
1. Creates Python venv, installs all deps
2. Builds C++ core with CMake
3. Downloads benchmark datasets
4. Installs frontend deps (npm install in app/frontend)
5. Runs smoke tests

### Development
```bash
# Run backend API (port 8000)
cd app/backend && uvicorn main:app --reload

# Run frontend dev server (port 5173)
cd app/frontend && npm run dev

# Run correctness tests
python -m pytest tests/test_correctness.py -v

# Run full benchmark suite (takes ~10 min)
python benchmarks/run_benchmarks.py --full

# Run quick benchmarks (takes ~1 min)
python benchmarks/run_benchmarks.py --quick
```

### Building for Demo
```bash
# Build frontend production bundle
cd app/frontend && npm run build

# Start production server
cd app/backend && uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 9. CODING STANDARDS

### Python
- Type hints everywhere — no untyped functions
- Docstrings on every class and public method
- Max function length: 50 lines (split if longer)
- No global mutable state except the engine instance
- f-strings for formatting, never % or .format()

### TypeScript / React
- Functional components only, no class components
- Custom hooks for all stateful logic (`useGraphEngine`, `useBenchmark`, etc.)
- Three.js objects cleaned up in `useEffect` return
- No `any` types — if you don't know the type, define an interface
- Component files: one component per file, named same as file

### C++
- C++20 features allowed (concepts, ranges, etc.)
- `const` everywhere possible
- RAII for all resources
- `[[nodiscard]]` on all functions returning error codes
- Clang-format with Google style

### Git Commits
```
feat: add heat-based promotion to F₁
fix: correct stale flush scope bounding
bench: add Zipf(1.2) workload benchmark
docs: update algorithm explanation for professor
test: add property-based triangle inequality test
```

---

## 10. WHAT TO BUILD — PRIORITY ORDER

Build in this exact order. Do not skip ahead.

```
Phase 1 — Algorithm (Week 1-2)
  [1] core/python/lct.py              — Link-Cut Tree
  [2] core/python/ett.py              — Euler Tour Tree  
  [3] core/python/heat_table.py       — Heat scoring
  [4] core/python/delta_ldb.py        — Delta-LDB queue
  [5] core/python/adaptskel.py        — Main engine
  [6] tests/test_correctness.py       — Oracle tests (must pass 100%)
  [7] core/python/baselines.py        — Dijkstra + networkx baselines

Phase 2 — Benchmarks (Week 3)
  [8]  benchmarks/generators/         — All 4 graph generators
  [9]  benchmarks/run_benchmarks.py   — Master runner
  [10] scripts/generate_figures.py    — Paper-quality plots

Phase 3 — Backend API (Week 4)
  [11] app/backend/main.py            — FastAPI server
  [12] app/backend/routers/           — All API endpoints
  [13] WebSocket streaming            — Live graph state to frontend

Phase 4 — Frontend Demo (Week 5-6)
  [14] app/frontend scaffold          — Vite + React + Three.js setup
  [15] GraphCanvas3D.tsx              — 3D graph renderer
  [16] Mode 1: Live Streaming         — Side-by-side comparison
  [17] Mode 2: Skeleton Explorer      — F₁/F₂ toggle visualization
  [18] Mode 3: Heat Map               — Live heat score visualization
  [19] Mode 4: Benchmark Arena        — Interactive benchmarking
  [20] Mode 5: Algorithm Explainer    — Step-through for mam
```

---

## 11. CONTEXT FOR CLAUDE CODE

### About the Student (Loki)
- 4th semester B.Tech CSE student at an Indian institution
- Strong in DSA and algorithms, comfortable with Python and C basics
- New to Three.js and advanced C++ — explain these when needed
- The project is graded: correctness > visual impressiveness > performance
- Mam (professor) will review: algorithm design, complexity analysis, code quality

### Tone of Communication
- Keep explanations simple and concrete — use examples like "Bengaluru traffic graph"
- Flag potential correctness bugs loudly before mentioning performance
- When stuck on the algorithm, debate approaches explicitly before committing
- Always verify the complexity claim matches the code before presenting to professor

### Known Challenges to Watch For
1. **LCT splay invariant** — easy to break during path operations; add assertions
2. **ETT level-raising** — the Holm et al. trick is subtle; implement slowly with tests at each step  
3. **Stale flush bounding** — the bounded Dijkstra scope must be proven, not assumed
4. **Three.js memory leaks** — dispose geometries and materials in useEffect cleanup
5. **WebSocket reconnection** — handle disconnects gracefully in the frontend

---

## 12. DEMO SCRIPT (FOR PRESENTATION)

When demoing to mam, follow this script:

1. **Open GRAPHSKEL** → Mode 1 (Live Streaming)
   - "This is a graph with [N] nodes and [M] edges being modified in real time"
   - Point to the timing bars: "ADAPTSKEL answers in Xμs, Dijkstra takes Yms — X× faster"

2. **Switch to Mode 2** (Skeleton Explorer)
   - "The blue edges form our skeleton F₁ — these are the hot, frequently-queried edges"
   - Toggle F₁ off: "Without the skeleton, this is just the cold residual F₂"
   - Run a query: "Watch the path pulse through the skeleton — answered in O(log n)"

3. **Switch to Mode 3** (Heat Map)
   - "Watch the Zipf distribution form — a few edges get very hot, most stay cold"
   - "This is exactly the power-law distribution seen in real road networks"

4. **Switch to Mode 4** (Benchmark Arena)
   - Set size to 10,000 nodes, click Run
   - "As the graph grows, Dijkstra's time grows as O(n log n) — this red line"
   - "ADAPTSKEL stays nearly flat — O(log² n)"

5. **Switch to Mode 5** (Explainer)
   - "Here is exactly what happens when we insert edge (u,v)..."
   - Walk through the step-by-step animation

---

*CLAUDE.md v1.0 — ADAPTSKEL Project — May 2026*
*Read PRD.md for full product requirements and algorithm specification*
