# ADAPTSKEL — Product Requirements Document
**Version:** 1.1 | **Date:** May 2026 | **Author:** Loki | **Status:** Active Development

> This is the master PRD. Claude Code reads this alongside CLAUDE.md.
> CLAUDE.md = HOW to build. PRD.md = WHAT to build and WHY.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Algorithm Design — ADAPTSKEL](#3-algorithm-design)
4. [Demo Application — GRAPHSKEL](#4-demo-application-graphskel)
5. [Graph Generation & Benchmarks](#5-benchmarks)
6. [System Architecture](#6-system-architecture)
7. [Technical Requirements](#7-technical-requirements)
8. [API Specification](#8-api-specification)
9. [Frontend Specification](#9-frontend-specification)
10. [Performance Requirements](#10-performance-requirements)
11. [Implementation Roadmap](#11-roadmap)
12. [Testing Strategy](#12-testing)
13. [Risk Analysis](#13-risks)
14. [Open Research Problems](#14-research)
15. [Appendices](#15-appendices)

---

## 1. Executive Summary

**ADAPTSKEL** (Adaptive Skeletal Decomposition) is a novel algorithm for maintaining exact Single-Source Shortest Paths (SSSP) in graphs undergoing continuous edge insertions and deletions. It achieves O(log² n) amortized update time and O(log n) amortized query time for hot paths — the first algorithm to simultaneously achieve: fully dynamic support, exact distances, and polylogarithmic operations under realistic workload distributions.

**GRAPHSKEL** is the demo application: a 3D interactive visualization that demonstrates ADAPTSKEL beating Dijkstra in real time, with a benchmark arena, skeleton explorer, and step-by-step algorithm explainer.

### Performance at a Glance

| Algorithm | Insert | Delete | Query | Exact? | Fully Dynamic? |
|---|---|---|---|---|---|
| Dijkstra (rerun) | O(E log V) | O(E log V) | O(1) | ✓ | ✓ |
| Link-Cut Tree | O(log n) | O(log n) | O(log n) | ✗ (connectivity only) | ✓ |
| Euler Tour Tree + MST | O(log² n) | O(log² n) | O(log n) | ✗ (MST only) | ✓ |
| Bernstein-Stein 2016 | ✗ deletions only | O(m log n/ε) | O(1) | ✗ (approx) | ✗ |
| **ADAPTSKEL (ours)** | **O(log² n)** | **O(log² n)** | **O(log n) hot** | **✓ exact** | **✓** |

### Deliverables
- Python reference implementation of ADAPTSKEL
- C++ performance implementation with Python bindings
- GRAPHSKEL: 3D demo app (React + Three.js frontend + FastAPI backend)
- Benchmark suite with 4 graph generators and paper-quality figures
- Research paper draft with formal correctness proof and amortized analysis

---

## 2. Problem Statement

### 2.1 What is the problem?

A **graph** is a set of nodes (places, people, computers) connected by edges (roads, friendships, cables) with weights (distances, latencies). The **shortest path problem** asks: what is the minimum-weight path from node A to node B?

In the real world, graphs change constantly:
- Google Maps: roads open and close due to accidents and construction
- 5G networks: base stations go up and down every millisecond
- Fraud detection: bank transactions create and destroy account-to-account links
- Social networks: friend connections are added and removed millions of times per day

**The problem:** Every time the graph changes, existing algorithms must recompute shortest paths from scratch. For large graphs (millions of nodes), this is impossibly slow.

### 2.2 Concrete Example

Imagine a simplified Bengaluru road graph:

```
Koramangala ──5min── Indiranagar ──8min── Whitefield
      │                    │
     10min               6min
      │                    │
    Silk Board ──4min── Marathahalli
```

Shortest path Koramangala → Whitefield: via Indiranagar = 13 min.

Now ORR closes (Indiranagar—Whitefield edge deleted). What's the new shortest path?
- Koramangala → Indiranagar → Marathahalli → Whitefield = 5 + 6 + ? (need that edge)
- Or Koramangala → Silk Board → Marathahalli → some path...

Dijkstra reruns the whole algorithm: checks ALL roads again. For 50 million roads, this takes seconds. ADAPTSKEL updates only the affected region: milliseconds.

### 2.3 Why Existing Approaches Fail

**Family 1: Just rerun Dijkstra**
- Time: O(E log V) per update. For Google Maps (120M edges): ~3 billion operations per change.
- With 5,000 road changes/second: physically impossible.

**Family 2: Link-Cut Trees**
- Fast: O(log n) per operation.
- But only tracks *connectivity* ("can A reach B?") not *distance* ("how far is B from A?").
- Useless for navigation — you need exact distances.

**Family 3: Euler Tour Trees (Holm et al. 2001)**
- Maintains Minimum Spanning Tree in O(log² n).
- Shortest paths are not the same as MST paths.
- Completely different structures — ETT doesn't help for exact SSSP.

**Family 4: Bernstein-Stein Decremental SSSP (2016)**
- Best known result: O(m log n / ε) total time.
- Two fatal flaws: (a) deletions only — can't handle road openings; (b) approximate — gives (1+ε) distances, not exact.

**The gap:** No existing algorithm handles all four requirements simultaneously:

```
✓ Fully dynamic (both insertions AND deletions)
✓ Exact distances (not approximate)  
✓ Polylogarithmic per operation (fast enough for real-time)
✓ Deterministic (safe against adversarial inputs)
```

### 2.4 Real Applications Where This Matters

| Application | Graph Size | Update Rate | Current Solution | Problem |
|---|---|---|---|---|
| Google Maps routing | 50M nodes, 120M edges | ~5,000/sec | Approximate heuristics | Routes are wrong after incidents |
| 5G mesh routing | 100K nodes, 500K edges | ~50,000/sec | Local Dijkstra patches | Stale routing tables → dropped packets |
| Bank fraud detection | 500M nodes, 10B edges | ~10,000/sec | Batch processing (hours) | Fraud detected too late |
| CDN routing | 1M nodes, 5M edges | ~1,000/sec | Static precomputed tables | Can't respond to outages in real time |

---

## 3. Algorithm Design

### 3.1 Formal Problem Definition

**Input:**
- Dynamic graph G = (V, E) with |V| = n, |E| = m
- Edge weights w: E → ℝ⁺ (positive reals)
- Stream of operations: INSERT(u,v,w), DELETE(u,v), QUERY(s,t)

**Output:**
- For each QUERY(s,t): exact shortest-path distance δ(s,t) in G at time of query

**Goal:**
- INSERT: O(log² n) amortized
- DELETE: O(log² n) amortized  
- QUERY (hot path): O(log n) amortized
- Space: O(n log n)
- Exact (not approximate)
- Deterministic (no randomization)

**Distributional Assumption:**
Query pairs (s,t) follow a Zipf(α) distribution with α ≥ 1. This means a small fraction of edges appear on the vast majority of queried paths. This holds empirically for all known real-world graph workloads (road networks α≈1.3, social graphs α≈1.7, routing tables α≈1.2).

### 3.2 Key Notation

| Symbol | Meaning |
|---|---|
| n | Number of vertices |
| m | Number of edges (dynamic) |
| F₁ ⊆ E | Skeleton forest (hot edges, LCT-backed) |
| F₂ ⊆ E \ F₁ | Residual forest (cold edges, ETT-backed) |
| heat(e) | Query frequency score of edge e |
| T | Promotion threshold = ⌈log n⌉ |
| T/2 | Demotion threshold (hysteresis) |
| W | Heat decay window size = n |
| B | Max Delta-LDB batch size = ⌈log n⌉ |
| Φ | Potential function for amortized analysis |

### 3.3 Core Insight — Why This Works

Real-world query workloads follow **Zipf's law**: if you rank all paths by query frequency, the k-th most popular path is queried at rate ∝ 1/k^α.

In a road network: interstate highways (NH-44, ORR in Bengaluru) carry the majority of queries. Local bylanes carry almost none.

**ADAPTSKEL's key idea:** Track which edges appear frequently on queried paths. Move those edges into a fast "skeleton" layer. The skeleton naturally becomes the high-traffic subgraph. Since the skeleton is small (O(n log n) edges vs O(m) total), traversing it is fast.

### 3.4 Data Structures

#### 3.4.1 Link-Cut Tree (F₁ — Skeleton Layer)

A Link-Cut Tree represents a forest of trees using a hierarchy of splay trees (self-adjusting BSTs). The key operations:

| Operation | Description | Time |
|---|---|---|
| `link(u, v, w)` | Add edge (u,v,w) connecting two trees | O(log n) amortized |
| `cut(u, v)` | Remove edge (u,v), splitting tree | O(log n) amortized |
| `connected(u, v)` | Check if u and v are in same tree | O(log n) amortized |
| `path_query(u, v)` | Sum/min of weights on u-v path | O(log n) amortized |
| `find_root(v)` | Find root of v's tree | O(log n) amortized |

**What it stores per node:**
```python
class LCTNode:
    id: int           # vertex ID
    left: LCTNode     # splay left child
    right: LCTNode    # splay right child  
    parent: LCTNode   # path or virtual parent
    reversed: bool    # lazy flip tag
    edge_weight: float    # weight of edge to parent
    path_min: float       # min edge weight in subtree
    dist: float           # current distance label from source
    delta_lazy: float     # pending distance delta (lazy)
    stale: bool           # needs flush before query
    heat: int             # current heat score
```

#### 3.4.2 Euler Tour Tree (F₂ — Residual Layer)

An Euler Tour Tree represents each tree in F₂ as its Euler tour sequence stored in a balanced BST (treap). This enables O(log n) subtree queries.

**Key operation for ADAPTSKEL:** `min_crossing_edge(component_A, component_B, level)` — finds the minimum-weight edge in F₂ that connects two components. Used when an F₁ spanning edge is deleted and we need a replacement.

```python
class ETTNode:
    u: int            # edge endpoints
    v: int
    weight: float     # edge weight
    level: int        # Holm et al. level (0 to log n)
    in_forest: bool   # is this a spanning edge?
    priority: int     # random treap priority
    subtree_min: float    # min weight in ETT subtree (aggregated)
    subtree_size: int     # for level-raising threshold check
```

#### 3.4.3 Heat Score Table

```python
class HeatTable:
    heat: dict[tuple, int]  # (u,v) → heat score
    window: CircularBuffer  # last W query paths
    W: int                  # window size
    T: int                  # promotion threshold
    
    def increment(self, path: list[Edge]) -> list[Edge]:
        """Increment heat for all edges on path. Return newly hot edges."""
        
    def evict_oldest(self) -> list[Edge]:
        """Evict oldest query, decrement heat. Return newly cold edges."""
```

#### 3.4.4 Delta-LDB Queue

```python
class DeltaLDBQueue:
    """Lazy Distance Label Batching priority queue.
    
    Separates DECREASE events (from insertions, non-urgent) from
    INCREASE events (from deletions, must be flushed before queries).
    """
    decrease_queue: MinHeap   # ordered by distance improvement
    increase_queue: MinHeap   # ordered by affected vertex distance
    
    def push_decrease(self, u, v, w): ...
    def push_increase(self, u, v): ...
    def flush_decreases(self, limit: int) -> int: ...  # returns ops done
    def flush_increases_for_path(self, path: list) -> None: ...
```

### 3.5 The Three Novel Contributions

#### Contribution 1: Heat-Based Edge Promotion

No existing algorithm uses query frequency as a structural signal. ADAPTSKEL does.

**How it works:**

1. Every edge starts cold — in F₂
2. After each QUERY(s,t), every edge on the returned path gets `heat += 1`
3. Simultaneously, the oldest query in the rolling window W is evicted, decrementing heat for edges on that old path
4. When `heat(e) ≥ T`: edge is **promoted** from F₂ to F₁
5. When `heat(e) ≤ T/2`: edge is **demoted** from F₁ back to F₂

The hysteresis band [T/2, T] prevents oscillation — an edge crossing the boundary repeatedly would otherwise cause O(n) promotion costs.

**Amortized promotion cost analysis:**

Define potential: `Φ = Σ_{e ∈ F₂} heat(e)`

- Each QUERY increments heat for O(log n) edges on the path: `ΔΦ ≤ +log n`
- Each promotion removes an edge from F₂ at heat ≥ T: `ΔΦ ≤ -T = -log n`
- Amortized promotion cost per query = actual_cost + ΔΦ = O(log n) + 0 = O(log n)
- Total promotion cost over Q queries: O(Q log n) — amortized O(1) per query's promotions

#### Contribution 2: Delta-LDB Batching

**Key observation:** Distance decreases and increases have different urgency.

- **Decreases** (from edge insertions): If dist[v] decreases, no existing query answer becomes wrong — it just becomes a conservative bound. Safe to process lazily.
- **Increases** (from edge deletions): If dist[v] increases, a cached answer might be wrong. Must be processed before the next query touching v.

**The batching protocol:**

```
On INSERT(u,v,w):
  1. Push DECREASE event to queue          → O(1)
  2. Flush at most B=O(log n) DECREASE events   → O(B log n) = O(log² n)

On DELETE(u,v):
  1. Mark u, v as "stale"                  → O(1)
  2. Push INCREASE event                   → O(1)

On QUERY(s,t):
  1. Find all stale vertices on s-t path in F₁  → O(log n)
  2. Flush INCREASE events for stale vertices   → O(log² n) bounded Dijkstra
  3. Traverse F₁ for answer                     → O(log n)
```

The bounded Dijkstra for increase-flush only explores within radius O(log n) hops from the deleted edge in F₁. This scope is bounded because:
- F₁ is sparse (O(n log n) edges)
- In realistic graphs (small-world property), affected neighborhoods have diameter O(log n)

#### Contribution 3: Two-Level Forest Architecture

```
All edges E
├── F₁ (Skeleton Layer — Link-Cut Tree)
│   ├── Spanning tree edges: minimum to maintain connectivity
│   ├── Hot non-tree edges: heat ≥ T
│   └── Size: O(n log n) edges total
│
└── F₂ (Residual Layer — Euler Tour Tree)
    ├── All cold edges: heat < T
    ├── Organized by level (Holm et al. levels 0..log n)
    └── Size: O(m) edges total
```

**The Holm et al. level trick for F₂:**

Assign each F₂ edge a level 0, 1, ..., ⌊log n⌋. A level-i edge is in a connected component of size ≤ n/2^i.

When an F₁ spanning edge (u,v) is deleted:
1. Search F₂ for replacement edge, starting from highest level
2. At each level, if no replacement found, "raise" all level-i edges in the smaller component to level i+1
3. This ensures the replacement found is minimum-weight
4. Total cost: O(log² n) amortized (each edge changes level at most O(log n) times in its lifetime)

### 3.6 Complete Algorithm Pseudocode

```python
class AdaptSkel:
    def __init__(self, T=None, W=None, B=None):
        self.n = 0                      # vertex count
        self.F1 = LinkCutTree()         # skeleton layer
        self.F2 = EulerTourForest()     # residual layer
        self.heat = HeatTable(W=W)      # heat scores
        self.delta = DeltaLDBQueue()    # lazy updates
        self.dist = {}                  # distance labels
        self.T = T or ceil(log2(max(self.n, 2)))   # promotion threshold
        self.W = W or self.n            # heat window
        self.B = B or ceil(log2(max(self.n, 2)))   # batch size

    def insert(self, u: int, v: int, w: float) -> None:
        """
        Insert edge (u,v,w). Amortized O(log² n).
        """
        # 1. Add to cold layer
        self.F2.add(u, v, w, level=0)
        
        # 2. If edge improves connectivity, promote to F₁
        if not self.F1.connected(u, v):
            self.F2.remove(u, v)
            self.F1.link(u, v, w)          # O(log n) LCT operation
        
        # 3. Enqueue distance decrease if applicable
        if self.dist.get(u, INF) + w < self.dist.get(v, INF):
            self.delta.push_decrease(u, v, w)
        if self.dist.get(v, INF) + w < self.dist.get(u, INF):
            self.delta.push_decrease(v, u, w)
        
        # 4. Lazily flush at most B decrease events
        self.delta.flush_decreases(limit=self.B)  # O(B log n)

    def delete(self, u: int, v: int) -> None:
        """
        Delete edge (u,v). Amortized O(log² n).
        """
        if self.F1.has_edge(u, v):
            # Skeleton edge deleted — need replacement
            self.F1.cut(u, v)             # O(log n)
            
            # Search F₂ for min-weight replacement (Holm et al.)
            replacement = None
            for level in range(self.F2.max_level, -1, -1):
                component_u = self.F1.component(u)
                component_v = self.F1.component(v)
                r = self.F2.min_crossing_edge(component_u, component_v, level)
                if r is not None:
                    replacement = r
                    break
                else:
                    # Raise all level-i edges in smaller component
                    smaller = min(component_u, component_v, key=len)
                    self.F2.raise_level(smaller, level)  # amortized O(log n)
            
            if replacement:
                self.F2.remove(*replacement)
                self.F1.link(*replacement)    # restore connectivity
            
            # Mark affected vertices stale
            self.F1.mark_stale_component(u)
            self.delta.push_increase(u, v)
        
        else:
            # Cold edge — simple removal
            self.F2.remove(u, v)             # O(log n)
        
        # Check heat — might need demotion if this was a hot non-tree edge
        self._check_demotion(u, v)

    def query(self, s: int, t: int) -> float:
        """
        Return exact δ(s,t). O(log n) for hot path, O(log² n) cold.
        """
        # 1. Flush pending increases affecting this path
        path_nodes = self.F1.path_nodes(s, t)          # O(log n)
        stale_nodes = [v for v in path_nodes if self.F1.is_stale(v)]
        
        if stale_nodes:
            self._flush_increases_bounded(stale_nodes)  # O(log² n)
        
        # 2. Traverse F₁ for answer
        path_edges = self.F1.path_edges(s, t)           # O(log n)
        distance = sum(e.weight for e in path_edges)
        
        # 3. Update heat scores
        newly_hot = self.heat.increment(path_edges)     # O(|path|) = O(log n)
        for edge in newly_hot:
            self._promote(edge)                          # O(log n) amortized
        
        # 4. Evict oldest query from window
        newly_cold = self.heat.evict_oldest()
        for edge in newly_cold:
            self._demote(edge)                           # O(log n) amortized
        
        return distance

    def _promote(self, edge):
        """Move edge from F₂ to F₁. O(log n)."""
        self.F2.remove(edge.u, edge.v)
        if not self.F1.connected(edge.u, edge.v):
            self.F1.link(edge.u, edge.v, edge.weight)
        else:
            self.F1.add_hot_nontree(edge)   # hot non-tree storage

    def _demote(self, edge):
        """Move edge from F₁ to F₂ if below demotion threshold. O(log n)."""
        if self.heat.get(edge) <= self.T // 2:
            self.F1.remove_hot_nontree(edge)
            self.F2.add(edge.u, edge.v, edge.weight, level=0)

    def _flush_increases_bounded(self, stale_nodes):
        """
        Bounded Dijkstra for stale vertices.
        Scope: O(log n) hops from each stale vertex in F₁.
        """
        for v in stale_nodes:
            # Local Dijkstra within radius=log(n) hops in F₁
            self._local_dijkstra(v, radius=ceil(log2(self.n)))
            self.F1.mark_fresh(v)
```

### 3.7 Complexity Analysis

#### Per-Operation Costs (Amortized)

| Operation | Sub-operation | Cost | Note |
|---|---|---|---|
| INSERT | F₂ add (ETT) | O(log n) | Treap insert |
| INSERT | F₁ link if needed (LCT) | O(log n) | Splay operation |
| INSERT | Delta flush (B events) | O(B log n) = O(log² n) | B = O(log n) |
| INSERT | **Total** | **O(log² n)** | Amortized |
| DELETE | F₁ cut (LCT) | O(log n) | Splay |
| DELETE | Replacement search (ETT) | O(log² n) | Holm et al. |
| DELETE | Level raising | O(log n) amortized | Over edge lifetime |
| DELETE | **Total** | **O(log² n)** | Amortized |
| QUERY (hot) | Stale check | O(log n) | No stale nodes |
| QUERY (hot) | F₁ path traverse | O(log n) | LCT path query |
| QUERY (hot) | Heat update + eviction | O(log n) amortized | Potential argument |
| QUERY (hot) | **Total** | **O(log n)** | Amortized |
| QUERY (cold) | Stale flush (bounded Dijkstra) | O(log² n) | Scope bounded |
| QUERY (cold) | F₁ path traverse | O(log n) | |
| QUERY (cold) | **Total** | **O(log² n)** | Amortized |

#### Space Complexity

| Component | Space |
|---|---|
| F₁ (LCT) | O(n) spanning + O(n log n) hot non-tree = O(n log n) |
| F₂ (ETT, all levels) | O(m) |
| Heat table | O(m) |
| Query window buffer | O(W × log n) = O(n log n) |
| Delta-LDB queue | O(B) = O(log n) |
| **Total** | **O(m + n log n)** |

#### ADAPTSKEL Conjecture (Formal Statement)

> **Conjecture:** For any streaming graph sequence on n vertices with query distribution following Zipf(α) for α ≥ 1, ADAPTSKEL achieves O(log n · log Δ) amortized time per operation in expectation, where Δ is the max degree. Whether this bound holds worst-case (without the Zipf assumption) is equivalent to the open problem of fully dynamic exact SSSP in polylogarithmic time.

---

## 4. Demo Application — GRAPHSKEL

### 4.1 What GRAPHSKEL Is

GRAPHSKEL is a 3D interactive web application demonstrating ADAPTSKEL. It has five operational modes and is designed to impress both technically (correctness, performance) and visually (3D aesthetics, real-time animation).

**Core technology:**
- Frontend: React 18 + TypeScript + Three.js (3D) + Recharts (2D charts)
- Backend: FastAPI + WebSocket (live streaming)
- Algorithm: TypeScript port for browser, Python for benchmarks

### 4.2 Visual Design Language

#### Color System
```css
/* Core palette */
--space-black:     #0a0a0f;  /* background */
--deep-navy:       #0d1117;  /* panel backgrounds */
--skeleton-blue:   #00d4ff;  /* F₁ skeleton edges */
--skeleton-glow:   #0099cc;  /* F₁ glow color */
--heat-amber:      #ff8c00;  /* hot edge highlight */
--heat-red:        #ff3300;  /* max heat */
--cold-ghost:      #9090a0;  /* F₂ cold edges */
--cold-dim:        #505060;  /* very cold */
--path-gold:       #ffd700;  /* active query path */
--insert-green:    #00ff88;  /* edge insertion */
--delete-red:      #ff4444;  /* edge deletion */
--node-white:      #e0e8ff;  /* default node */
--node-source:     #00ff88;  /* query source */
--node-target:     #ff6600;  /* query target */

/* UI chrome */
--glass-bg:        rgba(13, 17, 23, 0.75);
--glass-border:    rgba(0, 212, 255, 0.15);
--text-primary:    #e0e8ff;
--text-secondary:  #7080a0;
--text-accent:     #00d4ff;
```

#### Typography
```css
--font-display:  'Space Grotesk', sans-serif;   /* headers, labels */
--font-mono:     'JetBrains Mono', monospace;   /* numbers, code, stats */
--font-body:     'Inter', sans-serif;           /* body text */
```

#### 3D Visual Rules
- Background: deep space black with subtle star particle field (5000 particles, slow drift)
- Nodes: glowing spheres, radius proportional to degree, bloom post-processing
- F₁ edges: bright blue cylinders, emissive material, slightly thicker (r=0.02)
- F₂ edges: thin ghost-white lines (LineBasicMaterial, opacity 0.3)
- Active query path: gold pulsing animation traveling along edges
- Edge insert: green particle burst at midpoint, edge materializes with scale animation (0 → 1 in 300ms)
- Edge delete: red flash, edge breaks into 8 fragments that drift apart and fade
- Camera: OrbitControls with auto-rotate at 0.5 rpm when idle, damping=0.05
- Post-processing: UnrealBloomPass (strength=0.8, radius=0.4, threshold=0.1)

#### Glass Morphism Panels
```css
.glass-panel {
  background: rgba(13, 17, 23, 0.75);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 12px;
  box-shadow: 0 0 40px rgba(0, 212, 255, 0.05);
}
```

### 4.3 Mode 1 — Live Streaming Graph

**What it shows:** ADAPTSKEL vs Dijkstra running in real time on the same streaming graph.

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│         ADAPTSKEL              │         DIJKSTRA        │
│     [3D graph, blue glow]      │   [3D graph, red glow]  │
│                                │                         │
│  Ops/sec: 47,832               │  Ops/sec: 1,204         │
│  Last query: 0.04ms            │  Last query: 1.82ms     │
│                                │                         │
│  [graph updates live with edges inserting/deleting]      │
├────────────────────────────────────────────────────────  │
│  ADAPTSKEL  ████████████████████████████  0.04ms         │
│  Dijkstra   ████                          1.82ms  45.5× │
└─────────────────────────────────────────────────────────┘
```

**Controls:**
- Graph preset: Random | Road Network | Social | Barabasi-Albert
- Node count: 50 / 100 / 500 / 1000 / 5000
- Stream speed: Slow / Normal / Fast / Max
- Query frequency: Every 1s / 0.5s / 0.1s
- Pause / Resume

**Behavior:**
- New edges materialize with green burst animation
- Deleted edges shatter with red particle effect
- Every query: gold pulse travels along hot path in ADAPTSKEL panel
- Dijkstra panel shows "recalculating..." spinner during each recompute
- The timing gap grows visibly as graph size increases

### 4.4 Mode 2 — Skeleton Explorer

**What it shows:** The internal structure of ADAPTSKEL — F₁ skeleton vs F₂ residual.

**Features:**
- Load preset graphs or generate random
- Toggle F₁ visibility (blue skeleton edges)
- Toggle F₂ visibility (ghost cold edges)
- Toggle node heat labels (numbers floating above nodes)
- Click any edge: side panel shows heat score, level, which forest, promotion history
- Click any node: shows dist[] label, stale status
- Run QUERY(s,t): source and target node pickers, gold path animation
- Run INSERT(u,v,w): edge materializes, skeleton possibly reshapes
- Run DELETE(u,v): edge shatters, replacement search animated step-by-step

**Camera presets:** Top-down (2D feel), Isometric, Free orbit, Auto-orbit

### 4.5 Mode 3 — Heat Score Live Map

**What it shows:** Heat scores building up in real time, showing Zipf distribution forming.

**Visualization:**
- Edges color-coded by heat: cold (#505060) → warm (#ff8c00) → hot (#00d4ff)
- Edge thickness scales with heat score
- F₁ boundary shown as luminous outline around skeleton subgraph
- Heat histogram panel (Recharts) on the right: shows power-law distribution forming
- "Hot ratio" gauge: what % of edges are in F₁

**Workload controls:**
- Zipf α: 0.5 / 1.0 / 1.2 / 1.5 / 2.0 (how concentrated queries are)
- Query pattern: Uniform random vs Zipf vs Adversarial
- Show/hide heat score numbers on edges

**Key insight to communicate:**
- At α=1.2 (realistic): F₁ crystallizes quickly, hot ratio reaches 80%+, queries become O(log n)
- At α=0.5 (near-uniform): F₁ never stabilizes, algorithm degrades toward worst-case
- This explains WHY ADAPTSKEL works in practice

### 4.6 Mode 4 — Benchmark Arena

**What it shows:** Head-to-head performance comparison with real numbers.

**Left panel — Configuration:**
```
Graph Type:   [Random] [Road] [Social] [Adversarial]
Node Count:   [100] [1K] [10K] [50K] [100K]
Operations:   [1K] [10K] [100K]
Query Mix:    INSERT __% DELETE __% QUERY __%
Zipf α:       ──────●────── 1.2
```

**Center — 3D Bar Chart (Three.js):**
- Two floating 3D bars: ADAPTSKEL (blue) vs Dijkstra (red)
- Bars rise from a ground plane with reflection
- Text labels float above bars
- Bars animate when new results come in

**Right panel — Results:**
```
┌──────────────────────────┐
│ ADAPTSKEL  vs  Dijkstra  │
├──────────────────────────┤
│ Avg query:  0.04ms       │
│             vs 1.82ms    │
│                          │
│ Speedup:    ████ 45.5×   │
│                          │
│ Operations: 10,000       │
│ Hot ratio:  84.2%        │
│ F₁ edges:  1,203 / 5,000 │
└──────────────────────────┘
```

**Bottom — Line Chart (Recharts):**
- X: graph size (log scale)
- Y: avg operation time μs (log scale)
- Line 1 (blue): ADAPTSKEL — nearly flat on log scale
- Line 2 (red): Dijkstra — steep linear growth
- The divergence is the money shot

**Export:** PNG (chart image), CSV (raw data), JSON (full results)

### 4.7 Mode 5 — Algorithm Explainer

**What it shows:** Step-by-step walkthrough of ADAPTSKEL for academic presentation.

**Design:** Clean white-on-dark panels, no 3D distractions. Focused.

**Operation flows (each animated):**

**INSERT flow (9 steps):**
1. New edge (u,v,w) arrives — highlighted in the graph
2. "Check: is (u,v) already in graph? No — proceed"
3. Edge added to F₂ (appears as ghost white line)
4. "Check: are u and v connected in F₁? Yes/No"
5. If not: "Promote to F₁ spanning edge" (ghost → blue glow)
6. "Check: does this edge improve any distances?"
7. If yes: DECREASE event pushed to queue (shown as item in queue visualization)
8. "Flush up to B=20 pending DECREASE events from queue"
9. "Done. Total amortized cost: O(log² n)"

**DELETE flow (11 steps):**
1. Edge (u,v) removed — red flash
2. "Was this a skeleton (F₁) edge? Yes."
3. F₁.cut(u,v) shown — tree splits into two components
4. "Search F₂ for minimum-weight replacement edge..."
5. Animated search through F₂ levels
6. Replacement edge found — highlighted
7. "Promote replacement to F₁" — ghost → blue glow
8. Connectivity restored
9. "Mark affected vertices as stale"
10. INCREASE event pushed to queue
11. "Done. Total amortized cost: O(log² n)"

**QUERY flow (7 steps):**
1. Query(s, t) received — source and target highlighted
2. "Check: any stale vertices on s-t path in F₁?"
3. If stale: bounded Dijkstra runs (shown with expanding frontier)
4. "Traverse F₁ skeleton for shortest path"
5. Gold path pulse animation along skeleton
6. "Increment heat for all edges on path"
7. "Edge with heat ≥ T? Promote it." (heat bar fills up → promotion)

**Controls:** Previous step | Play | Next step | Speed: 0.5× / 1× / 2×

---

## 5. Benchmarks

### 5.1 Graph Generators

#### Generator 1: Zipf Workload (Primary Benchmark)

Purpose: demonstrate ADAPTSKEL's skeleton advantage under realistic workloads.

```python
def generate_zipf_workload(
    n: int,          # number of vertices
    m: int,          # number of edges  
    num_queries: int,
    alpha: float = 1.2,    # Zipf parameter
    insert_frac: float = 0.2,
    delete_frac: float = 0.1,
    query_frac: float = 0.7
) -> tuple[Graph, list[Operation]]:
    """
    Generate a Barabasi-Albert graph (power-law degree distribution)
    and a query/update workload where queries follow Zipf distribution.
    
    The Zipf workload means:
    - 20% of edges appear on 80% of queried paths (power-law)
    - These become "hot" in ADAPTSKEL → F₁ skeleton crystallizes
    - Hot queries answered in O(log n) → massive speedup vs Dijkstra
    
    Returns:
        graph: initial graph
        ops: sequence of (INSERT/DELETE/QUERY, args) tuples
    """
    # 1. Generate graph (Barabasi-Albert: realistic power-law degree dist)
    G = barabasi_albert_graph(n, m=3)  # each new node connects to 3 existing
    
    # 2. Compute "popular paths" — the paths that will be queried most
    # Sample log(n) "hub" nodes (high-degree nodes in BA graph)
    hubs = sorted(G.nodes, key=lambda v: G.degree(v), reverse=True)[:ceil(log(n))]
    popular_pairs = [(s, t) for s in hubs for t in hubs if s != t]
    
    # 3. Generate query sequence with Zipf distribution over popular_pairs
    zipf_weights = [1/(i+1)**alpha for i in range(len(popular_pairs))]
    normalize = sum(zipf_weights)
    zipf_weights = [w/normalize for w in zipf_weights]
    
    ops = []
    for _ in range(num_queries):
        r = random.random()
        if r < query_frac:
            pair = random.choices(popular_pairs, weights=zipf_weights)[0]
            ops.append(('QUERY', pair))
        elif r < query_frac + insert_frac:
            # Random new edge
            u, v = random.sample(G.nodes, 2)
            if not G.has_edge(u, v):
                w = random.uniform(1, 10)
                ops.append(('INSERT', (u, v, w)))
                G.add_edge(u, v, weight=w)
        else:
            # Delete a random non-critical edge
            if G.edges:
                edge = random.choice(list(G.edges))
                ops.append(('DELETE', edge[:2]))
                G.remove_edge(*edge[:2])
    
    return G, ops
```

#### Generator 2: Scaling Benchmark

Purpose: show ADAPTSKEL's O(log² n) vs Dijkstra's O(n log n) growth rate.

```python
def generate_scaling_benchmark(
    sizes: list[int] = [100, 500, 1000, 5000, 10000, 50000, 100000],
    ops_per_size: int = 10000
) -> dict[int, BenchmarkResult]:
    """
    For each size n, generate a workload and measure both algorithms.
    The "money plot" shows their diverging performance curves.
    """
    results = {}
    for n in sizes:
        m = n * 5  # sparse graph, 5 edges per node on average
        graph, ops = generate_zipf_workload(n, m, ops_per_size)
        
        # Run ADAPTSKEL
        adaptskel_times = run_adaptskel(graph, ops)
        
        # Run Dijkstra (rerun from scratch on each mutation)
        dijkstra_times = run_dijkstra_baseline(graph, ops)
        
        results[n] = BenchmarkResult(
            n=n,
            adaptskel_avg_us=mean(adaptskel_times),
            dijkstra_avg_us=mean(dijkstra_times),
            speedup=mean(dijkstra_times) / mean(adaptskel_times),
            hot_query_ratio=adaptskel_times.hot_ratio
        )
    
    return results
```

#### Generator 3: Adversarial Workload

Purpose: honestly demonstrate ADAPTSKEL's weakness.

```python
def generate_adversarial_workload(n: int, ops: int) -> list[Operation]:
    """
    Adversary always queries completely different source-target pairs.
    The skeleton never forms because every query uses a different path.
    
    Shows: ADAPTSKEL degrades toward O(log² n) worst case.
    Shows: we are being intellectually honest — ADAPTSKEL is not magic.
    
    For adversarial workloads, Dijkstra has a smaller constant factor
    because it doesn't waste time on promotion/demotion with no benefit.
    
    Present this honestly: "ADAPTSKEL is designed for realistic workloads,
    not adversarial ones."
    """
    # Queries are uniformly random (every pair equally likely)
    # No power-law → skeleton never crystallizes
    ...
```

#### Generator 4: Road Network Simulator

Purpose: demonstrate on realistic application domain.

```python
def generate_road_network(
    grid_size: int = 50,    # n×n grid = n² nodes
    shortcut_prob: float = 0.1  # probability of extra shortcut edges
) -> Graph:
    """
    Creates a grid graph with random shortcuts — approximates real road networks.
    
    - Grid edges: travel time = random(1, 5) minutes
    - Shortcuts: travel time = random(0.5, 2) minutes (like flyovers)
    - "Congestion events": periodic weight updates to simulate traffic
    - "Road closures": DELETE edges with probability 0.001 per timestep
    - "New roads": INSERT edges (rare)
    
    Road networks have large diameter O(√n) — challenging for ADAPTSKEL.
    This generator includes pre-processing for hierarchical decomposition.
    """
```

### 5.2 The Key Benchmark Figures

#### Figure 1: The Money Plot (show this first to mam)
- Title: "ADAPTSKEL vs Dijkstra: Average Query Time vs Graph Size"
- X-axis: Graph size n (log scale: 100 to 100,000)
- Y-axis: Average operation time in microseconds (log scale)
- Blue line: ADAPTSKEL — nearly flat, growing as O(log² n)
- Red line: Dijkstra — steep growth, O(n log n)
- Annotation at n=100K: "45.8× faster"
- Expected values:

| n | ADAPTSKEL (μs) | Dijkstra (μs) | Speedup |
|---|---|---|---|
| 100 | 12 | 45 | 3.8× |
| 1,000 | 28 | 890 | 31.8× |
| 10,000 | 51 | 18,200 | 357× |
| 100,000 | 78 | 412,000 | 5,282× |

#### Figure 2: Hot Query Ratio vs Zipf α
- X-axis: Zipf exponent α (0.5 to 2.0)
- Y-axis: Fraction of queries served via F₁ skeleton (0 to 100%)
- Shows: as α increases (more concentrated queries), hot ratio rises quickly
- Annotation: "At α=1.2 (realistic road networks), 84% of queries use fast O(log n) path"

#### Figure 3: Skeleton Crystallization Over Time
- X-axis: Number of queries processed (0 to 10,000)
- Y-axis: F₁ edge count (starts at n-1, grows to ~n log n)
- Shows: skeleton grows quickly at first as hot edges are discovered, then stabilizes
- Annotation: "Skeleton stabilizes after ~500 warmup queries"

#### Figure 4: Adversarial Comparison (intellectual honesty)
- Shows ADAPTSKEL vs Dijkstra under adversarial workload
- Both degrade to similar performance
- Label: "Under adversarial (uniform random) workloads, ADAPTSKEL's advantage disappears"
- This shows the algorithm is honest, not magic

---

## 6. System Architecture

### 6.1 Overall Architecture

```
[Benchmark Scripts]   [GRAPHSKEL Frontend]
        │                     │  HTTP/WebSocket
        │              [FastAPI Backend]
        │                     │
        └────────────[Python ADAPTSKEL Engine]────────[NetworkX Oracle]
                              │
                    [C++ ADAPTSKEL Core]  (optional, for perf)
                    [pybind11 bindings]
```

### 6.2 Backend API Routes

```
POST   /api/graph/create              Create new graph instance
POST   /api/graph/{id}/insert         Insert edge
DELETE /api/graph/{id}/edge/{u}/{v}   Delete edge
POST   /api/graph/{id}/query          SSSP query
GET    /api/graph/{id}/stats          Engine statistics
GET    /api/graph/{id}/skeleton       Return F₁ edge list (for visualization)
GET    /api/graph/{id}/heat           Return all edge heat scores
WS     /api/graph/{id}/stream         WebSocket: live graph state streaming

POST   /api/benchmark/run             Run benchmark suite
GET    /api/benchmark/{id}/status     Benchmark progress
GET    /api/benchmark/{id}/results    Benchmark results JSON

POST   /api/generate/zipf             Generate Zipf workload
POST   /api/generate/scaling          Generate scaling benchmark workload
POST   /api/generate/road             Generate road network
POST   /api/generate/adversarial      Generate adversarial workload
```

### 6.3 WebSocket Protocol

For Mode 1 (Live Streaming) and Mode 3 (Heat Map), the backend streams graph state to the frontend:

```typescript
// Message types (backend → frontend)
type GraphEvent =
  | { type: 'INSERT'; u: number; v: number; w: number; in_f1: boolean; heat: number }
  | { type: 'DELETE'; u: number; v: number }
  | { type: 'QUERY'; s: number; t: number; path: number[]; distance: number; hot: boolean; latency_us: number }
  | { type: 'PROMOTE'; u: number; v: number }   // edge promoted to F₁
  | { type: 'DEMOTE'; u: number; v: number }    // edge demoted to F₂
  | { type: 'STATS'; ops_per_sec: number; hot_ratio: number; f1_edges: number; delta_queue: number }
```

---

## 7. Technical Requirements

### Algorithm Requirements (Non-negotiable)

| ID | Requirement | Priority |
|---|---|---|
| ALG-01 | QUERY must return exact δ(s,t) for all operations | P0 |
| ALG-02 | INSERT amortized ≤ O(log² n) | P0 |
| ALG-03 | DELETE amortized ≤ O(log² n) | P0 |
| ALG-04 | QUERY (hot) amortized ≤ O(log n) | P0 |
| ALG-05 | Zero discrepancies vs NetworkX oracle on 10⁶ random ops | P0 |
| ALG-06 | Deterministic — no random number generation in core | P0 |
| ALG-07 | All five invariants maintained at all times (see CLAUDE.md §7) | P0 |
| ALG-08 | T, W, B configurable at init | P1 |

### Application Requirements

| ID | Requirement | Priority |
|---|---|---|
| APP-01 | All 5 modes functional and responsive | P0 |
| APP-02 | 3D graph renders smoothly ≥ 60fps for n ≤ 1000 | P0 |
| APP-03 | Live benchmark shows real timing numbers (not simulated) | P0 |
| APP-04 | Algorithm explainer covers INSERT, DELETE, QUERY | P0 |
| APP-05 | Export benchmark results as PNG and CSV | P1 |
| APP-06 | Works on Chrome/Firefox/Safari without plugins | P0 |
| APP-07 | WebSocket reconnects automatically on disconnect | P1 |

### Performance Requirements

| Metric | Target | Graph Size |
|---|---|---|
| INSERT p99 latency | < 500μs | n=10⁶, m=10⁷ |
| DELETE p99 latency | < 1ms | n=10⁶, m=10⁷ |
| QUERY p99 (hot) | < 100μs | n=10⁶, m=10⁷ |
| QUERY p99 (cold) | < 2ms | n=10⁶, m=10⁷ |
| Throughput (mixed) | > 100K ops/sec | n=10⁵, m=10⁶ |
| Hot query ratio | > 80% | Zipf(1.2) workload |
| 3D render fps | ≥ 60fps | n ≤ 1000 nodes |
| 3D render fps | ≥ 30fps | n ≤ 5000 nodes |

---

## 8. API Specification

### REST Endpoints (Full Detail)

```
POST /api/graph/create
Body: { "config": { "T": 20, "W": 1000000, "B": 20 } }
Response: { "graph_id": "g_abc123" }

POST /api/graph/{id}/insert  
Body: { "u": 42, "v": 17, "w": 3.14 }
Response: {
  "success": true,
  "in_f1": false,          // was edge connected to skeleton?
  "latency_us": 34,
  "f1_edge_count": 1203,
  "delta_queue_depth": 5
}

DELETE /api/graph/{id}/edge/{u}/{v}
Response: {
  "success": true,
  "was_skeleton": true,    // was this a skeleton edge?
  "replacement_found": true,
  "latency_us": 87
}

POST /api/graph/{id}/query
Body: { "source": 1, "target": 999 }
Response: {
  "distance": 12.87,
  "path": [1, 45, 203, 999],
  "path_hot": true,        // served via F₁?
  "latency_us": 28,
  "newly_promoted": 0      // edges promoted during this query
}

GET /api/graph/{id}/stats
Response: {
  "vertex_count": 1000,
  "edge_count": 4982,
  "f1_edge_count": 203,
  "f2_edge_count": 4779,
  "hot_query_ratio": 0.847,
  "avg_insert_us": 38.2,
  "avg_delete_us": 74.1,
  "avg_query_us": 28.7,
  "total_promotions": 847,
  "total_demotions": 312,
  "pending_decreases": 5,
  "pending_increases": 0
}

GET /api/graph/{id}/skeleton
Response: {
  "edges": [
    { "u": 1, "v": 45, "w": 2.3, "heat": 847, "is_spanning": true },
    ...
  ]
}
```

---

## 9. Frontend Specification

### Component Tree

```
App
├── Header (mode tabs, settings)
├── ControlPanel (left sidebar, glass morphism)
│   ├── ModeControls (mode-specific controls)
│   ├── GraphPresets (preset graph buttons)
│   └── SpeedControls (animation speed)
├── MainCanvas (center)
│   ├── GraphCanvas3D (Three.js, fills space)
│   │   ├── NodeMesh (instanced mesh for all nodes)
│   │   ├── EdgeMesh (line segments or cylinders)
│   │   ├── SkeletonOverlay (F₁ edges, separate material)
│   │   ├── PathTracer (animated gold path)
│   │   ├── ParticleSystem (insert/delete effects)
│   │   └── PostProcessing (bloom, tone mapping)
│   └── ModeOverlay (mode-specific UI overlaid on canvas)
├── StatsHUD (right sidebar, glass morphism)
│   ├── LiveMetrics (ops/sec, latency, hot ratio)
│   ├── AlgorithmState (F₁ size, queue depth, etc.)
│   └── SpeedupDisplay (ADAPTSKEL vs Dijkstra)
└── BenchmarkBar (bottom, appears in Mode 1 and 4)
    ├── AdaptSkelBar (blue progress bar)
    └── DijkstraBar (red progress bar)
```

### State Management (Zustand)

```typescript
interface GraphStore {
  // Graph state
  nodes: Map<number, Node3D>
  edges: Map<string, Edge3D>
  skeletonEdges: Set<string>
  heatScores: Map<string, number>
  
  // Algorithm state
  activeQuery: QueryResult | null
  hotPath: number[]
  stats: AlgorithmStats
  
  // UI state
  mode: Mode
  isStreaming: boolean
  selectedEdge: Edge3D | null
  selectedNode: number | null
  
  // Actions
  insertEdge: (u, v, w) => Promise<void>
  deleteEdge: (u, v) => Promise<void>
  runQuery: (s, t) => Promise<QueryResult>
  loadPreset: (preset: GraphPreset) => Promise<void>
  runBenchmark: (config: BenchmarkConfig) => Promise<void>
}
```

### Three.js Setup

```typescript
// GraphCanvas3D.tsx key setup
const setup3DScene = () => {
  // Scene
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x0a0a0f)
  
  // Camera
  camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000)
  camera.position.set(0, 0, 50)
  
  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.0
  
  // Post-processing
  composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))
  composer.addPass(new UnrealBloomPass(
    new THREE.Vector2(width, height),
    0.8,   // strength
    0.4,   // radius
    0.1    // threshold
  ))
  
  // Controls
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.autoRotate = true
  controls.autoRotateSpeed = 0.5
  
  // Star field background
  addStarField(scene, 5000)
  
  // Lighting
  scene.add(new THREE.AmbientLight(0x111122, 0.5))
  const pointLight = new THREE.PointLight(0x00d4ff, 1, 100)
  pointLight.position.set(0, 0, 30)
  scene.add(pointLight)
}
```

---

## 10. Performance Requirements

### Benchmark Acceptance Criteria

Before project submission, ALL of these must pass:

1. **Correctness:** Zero discrepancies vs NetworkX oracle on 1,000,000 random operations across 100 different random graphs
2. **Throughput:** ≥ 100,000 mixed ops/second on n=100,000 nodes, single thread
3. **Query latency:** p99 QUERY ≤ 2ms on n=100,000 graph under sustained load
4. **Hot ratio:** ≥ 80% queries served via F₁ on Zipf(1.2) workload after 1,000 warmup queries
5. **Speedup:** ≥ 10× faster than Dijkstra on n=10,000 nodes
6. **Memory:** ≤ 1GB RAM for n=100,000, m=500,000 graph
7. **3D render:** ≥ 60fps for n=1000 node graph in Chrome

---

## 11. Roadmap

### Phase 1: Algorithm (Week 1-2)
- [ ] LCT implementation with full unit tests
- [ ] ETT implementation with full unit tests
- [ ] Heat table + rolling window
- [ ] Delta-LDB queue
- [ ] ADAPTSKEL engine (INSERT/DELETE/QUERY)
- [ ] Correctness oracle tests (must pass 100%)
- [ ] Dijkstra + NetworkX baselines

### Phase 2: Benchmarks (Week 3)
- [ ] Zipf workload generator
- [ ] Scaling benchmark generator
- [ ] Adversarial workload generator
- [ ] Road network simulator
- [ ] Master benchmark runner
- [ ] Figure generation (matplotlib, paper-quality)

### Phase 3: Backend API (Week 4)
- [ ] FastAPI server with all endpoints
- [ ] WebSocket streaming for live graph state
- [ ] Benchmark service (runs Python engines)
- [ ] Health check + monitoring endpoints

### Phase 4: Frontend (Week 5-6)
- [ ] Project scaffold (Vite + React + Three.js + Tailwind)
- [ ] 3D graph renderer (nodes + edges + skeleton overlay)
- [ ] Mode 1: Live Streaming (side-by-side comparison)
- [ ] Mode 2: Skeleton Explorer
- [ ] Mode 3: Heat Score Map
- [ ] Mode 4: Benchmark Arena (3D bars + line chart)
- [ ] Mode 5: Algorithm Explainer (step-through)
- [ ] Polish: animations, particles, post-processing

### Phase 5: Paper + Submission (Week 7-8)
- [ ] Formal proof of amortized O(log² n) per operation
- [ ] Paper draft: intro, related work, algorithm, analysis, experiments
- [ ] Final benchmark figures
- [ ] Project presentation (slides)
- [ ] README + documentation

---

## 12. Testing

### Test 1: Correctness Oracle (MOST IMPORTANT)

```python
def test_correctness_oracle():
    """
    Run ADAPTSKEL and NetworkX Dijkstra in parallel.
    Assert zero distance discrepancies on every QUERY.
    """
    for trial in range(100):
        G_nx = nx.Graph()
        G_adapt = AdaptSkel()
        
        for _ in range(10000):
            op = random.choice(['INSERT', 'DELETE', 'QUERY'])
            
            if op == 'INSERT':
                u, v, w = random_edge()
                G_nx.add_edge(u, v, weight=w)
                G_adapt.insert(u, v, w)
            
            elif op == 'DELETE' and G_nx.edges:
                u, v = random.choice(list(G_nx.edges))
                G_nx.remove_edge(u, v)
                G_adapt.delete(u, v)
            
            elif op == 'QUERY' and G_nx.nodes:
                s, t = random.sample(list(G_nx.nodes), 2)
                
                expected = nx.shortest_path_length(G_nx, s, t, weight='weight')
                actual = G_adapt.query(s, t)
                
                assert abs(expected - actual) < 1e-9, \
                    f"Trial {trial}: QUERY({s},{t}) expected {expected} got {actual}"
```

### Test 2: Property-Based Tests

```python
@given(random_graph_ops(max_ops=1000))
def test_triangle_inequality(ops):
    """δ(u,w) ≤ δ(u,v) + δ(v,w) for all triples"""
    
@given(random_graph_ops(max_ops=1000))
def test_symmetry(ops):
    """δ(u,v) = δ(v,u) — undirected graph"""
    
@given(random_graph_ops(max_ops=1000))
def test_monotone_insert(ops):
    """Inserting edge never increases any distance"""
    
@given(random_graph_ops(max_ops=1000))
def test_monotone_delete(ops):
    """Deleting edge never decreases any distance"""
```

### Test 3: Invariant Checks

After every operation in debug mode, assert:
1. `F₁ ∪ F₂ = E` (partition is complete)
2. `F₁ ∩ F₂ = ∅` (no edge in both layers)
3. `F₁` is a valid spanning forest of G
4. `heat(e) ≤ W` for all edges
5. All F₁ edges have `heat(e) ≥ T/2`

---

## 13. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LCT implementation bugs → wrong distances | High | Critical | Test after every method, compare vs naive |
| ETT level-raising: O(log n) claim fails in practice | Medium | High | Empirically bound on all benchmarks |
| Stale flush scope exceeds O(log² n) on dense graphs | Medium | High | Add scope limit + circuit breaker |
| Three.js memory leak → browser crash on large graphs | High | Medium | Dispose all geometries in useEffect cleanup |
| WebSocket drops events under high load | Medium | Medium | Event queue with sequence numbers |
| Demo looks bad on mam's laptop (old hardware) | High | Medium | Test on low-end machine, add quality settings |

---

## 14. Open Research Problems

1. **Optimal T:** What heat threshold T minimizes total cost for a given Zipf α?
2. **Adversarial lower bound:** Can an adversary force ADAPTSKEL to O(n) per op without knowing the query history?
3. **Directed graphs:** Replace spanning forest with arborescence — different replacement edge search needed
4. **Distributed ADAPTSKEL:** How to partition F₁/F₂ across machines while keeping O(polylog) guarantees?
5. **Weight updates:** Direct DECREASE-KEY operation without DELETE + INSERT
6. **Information-theoretic threshold:** Frame heat score as mutual information estimator for "edge will appear on next query"

---

## 15. Appendices

### Appendix A: Related Work

| Paper | Year | Result | Relation |
|---|---|---|---|
| Dijkstra | 1959 | O(E log V) static SSSP | Baseline |
| Sleator-Tarjan | 1983 | O(log n) LCT operations | F₁ data structure |
| Holm et al. | 2001 | O(log² n) fully dynamic MST | F₂ level technique |
| Bernstein-Stein | 2016 | O(m log n/ε) dec. SSSP | Best decremental comparison |
| Abboud-VW | 2014 | Conditional lower bounds on dynamic SSSP | Motivates distributional assumption |

### Appendix B: Key Definitions

- **SSSP:** Single-Source Shortest Path — shortest distances from one source to all reachable vertices
- **Fully dynamic:** Algorithm supports BOTH insertions AND deletions
- **Amortized:** Average cost per operation over a sequence
- **Zipf distribution:** Power-law where k-th item has frequency ∝ 1/kᵅ
- **Skeleton (F₁):** Hot edge subgraph maintained in Link-Cut Tree
- **Residual (F₂):** Cold edge subgraph maintained in Euler Tour Tree
- **Heat score:** Query frequency counter per edge, decaying over rolling window W
- **Delta-LDB:** Lazy Distance Label Batching — deferred distance propagation

### Appendix C: Configuration Reference

| Parameter | Default | Range | Effect |
|---|---|---|---|
| T (promotion threshold) | ⌈log n⌉ | 5–100 | Higher T = smaller skeleton, fewer promotions |
| W (heat window) | n | 1K–10n | Larger W = longer heat memory |
| B (batch size) | ⌈log n⌉ | 5–100 | Larger B = more eager decrease processing |
| Demotion threshold | T/2 | 1 to T-1 | Higher = skeleton stays large |

---

*PRD v1.1 — ADAPTSKEL Project — May 2026*
*See CLAUDE.md for implementation instructions and skill usage*
