# ADAPTSKEL — Product Requirements Document v2.0
## COMPREHENSIVE EDITION — Complete with Docker & Deployment

**Version:** 2.0-Comprehensive | **Date:** June 2026 | **Author:** Pranav V. | **Status:** Active Development

---

## Executive Summary

**ADAPTSKEL** is a fully dynamic Single-Source Shortest Path (SSSP) algorithm achieving O(log² n) amortized insert/delete and O(log n) hot-path queries under Zipf-distributed workloads. This document provides complete technical specifications including algorithm design, 6-mode demo application, network routing system, and production-ready Docker containerization.

### Key Claims (Corrected from v1.1)

- **O(log n) hot queries:** Queries using skeleton edges (F₁) - most queries under Zipf
- **O(log² n) cold queries:** Queries avoiding skeleton (rare, bounded by Zipf)
- **O(log² n) per operation:** INSERT and DELETE operations
- **Exact distances:** Not approximate
- **Fully dynamic:** Both insertions AND deletions supported
- **Deterministic:** Safe for production use

### Three Deliverables

1. **GRAPHSKEL** - Interactive 3D visualization (6 visualization modes)
2. **Network Routing App** - ISP backbone routing system with real-time link failures (NEW)
3. **Docker Containerization** - Complete production deployment (embedded in this PRD)

---

## Problem Statement

### Real-World Context

Graphs change constantly in production:
- **Google Maps:** 5,000 road changes/sec (accidents, construction)
- **5G Networks:** 50,000 link changes/sec (base stations up/down)
- **ISP Routing:** 1,000 BGP updates/sec (link failures, reroutes)
- **Fraud Detection:** 10,000 account-link changes/sec (transactions)

**Problem:** Rerunning Dijkstra after each change is impossible. For 120M edges: O(E log V) = 3 billion operations per change × 5,000 changes/sec = 15 trillion ops/sec (physically impossible).

**Existing solutions fail:**
- **Dijkstra rerun:** O(E log V) per update - too slow
- **Link-Cut Trees:** O(log n) but only connectivity, not distances
- **ETT (MST):** O(log² n) but maintains spanning tree, not shortest paths
- **Bernstein-Stein:** Deletions only, approximate only

**ADAPTSKEL solution:** Leverage Zipf-distributed query workloads. Real graphs have natural hot/cold structure:
- **Hot edges:** Interstate highways, backbone fiber, celebrity connections (few)
- **Cold edges:** Local roads, access links, rare connections (many)

Maintain hot edges in fast data structure (Link-Cut Tree), handle cold edges lazily.

---

## Algorithm Design

### Formal Problem Definition

**Input:**
- Dynamic undirected weighted graph G = (V, E)
- |V| = n, |E| = m (both dynamic)
- Weights w: E → ℝ⁺
- Operations: INSERT(u, v, w), DELETE(u, v), QUERY(s, t)

**Output:**
- For each QUERY(s,t): return exact shortest-path distance δ(s,t)

**Complexity Goals:**
- INSERT: O(log² n) amortized
- DELETE: O(log² n) amortized
- QUERY (hot): O(log n) amortized
- QUERY (cold): O(log² n) amortized (rare)
- Space: O(m + n log n)

**Key Assumption:** Query pairs follow Zipf(α) distribution (α ≥ 1)
- Empirically validated: road networks α≈1.3, social α≈1.7, telecom α≈1.2

### Two-Layer Forest Architecture

#### F₁ — Skeleton Forest (Hot Edges)

**Data Structure:** Link-Cut Tree (Sleator-Tarjan 1983)

**Properties:**
- Stores edges with heat ≥ T (promotion threshold)
- O(log n) amortized per operation
- Operations: link(u,v,w), cut(u,v), path_query(u,v), find_root(v)

**Why LCT:** Fast exact path queries. When query(s,t) path lies in F₁, answer in O(log n).

#### F₂ — Residual Forest (Cold Edges)

**Data Structure:** Euler Tour Tree with Holm Levels

**Properties:**
- Stores edges with heat < T
- Maintains connectivity (not distances)
- Level structure enables O(log² n) replacement-edge finding

**Why ETT:** When skeleton edge deleted, replacement found in O(log² n).

### Heat Table & Promotion/Demotion

**Heat Scoring:**
```
heat[e] = count of last W queries using edge e

promotion:   heat[e] ≥ T        → move F₂ → F₁
demotion:    heat[e] ≤ T/2      → move F₁ → F₂
hysteresis:  T/2 < heat < T    → stable
```

**Self-tuning parameters:**
- T = ⌈log n⌉ (promotion threshold)
- W = n (heat window)
- T/2 (demotion with hysteresis)

### Delta-LDB (Lazy Distance Label Batching)

**Mechanism:**
- INCREASE events (deletions): process immediately
- DECREASE events (insertions): batch and flush B at a time
- Deferred decreases bounded by potential function

**Cost:** O(log² n) amortized per INSERT

---

## GRAPHSKEL Demo Application

Interactive 3D visualization with 6 modes demonstrating ADAPTSKEL on synthetic and real graphs.

### Mode 1: Live Streaming Graph
Side-by-side ADAPTSKEL vs Dijkstra comparison on streaming graph (30 nodes, 50 edges). Every 3 sec: random edge change. Every 2 sec: random query. Live timing bar shows latency gap growing.

### Mode 2: Skeleton Explorer
Static graph with layer inspection. Toggle F₁ (skeleton, electric blue) vs F₂ (cold, ghost white). Click edges for heat scores. Manual insert/delete, watch skeleton reshape.

### Mode 3: Heat Score Heatmap
Zipf(1.2) workload on graph. Heatmap overlay: white (cold) → amber → blue (hot). Watch F₁ crystallize. Bar chart shows heat distribution.

### Mode 4: Benchmark Arena
Choose graph type (random, road, social, adversarial) and size. Run 1000 mixed ops. Results: 3D floating bars (ADAPTSKEL vs Dijkstra), line chart (latency vs size), "X× faster" display.

### Mode 5: Algorithm Explainer
Step-through animation of INSERT/DELETE/QUERY. Each step narrates with text callouts. Shows data structure operations, cost breakdown.

### Mode 6: Network Routing App (NEW)
Real ISP backbone routing system. Map-based UI (OpenStreetMap). Cities as nodes, fiber links with latency. Poisson link failures (mean 1 per 100 sec). Route queries (e.g., NYC → LA). Metrics: convergence time (≤10ms), traffic loss (≤0.1%), path optimality (≥95%).

---

## Network Routing Application (NEW)

### Problem: ISP Backbone Resilience

An ISP backbone connects 50–200 cities with fiber links. Each link has latency, capacity, failure rate. Constraints:
- Route recalculated within < 10ms (before user perceives latency spike)
- Must handle 100–1,000 link changes/sec
- Routes must be valid (no loops, respect capacity)

**Old solution:** BGP + Dijkstra on each router → 50ms+ → traffic oscillates.
**ADAPTSKEL advantage:** Hot links (core backbone) pre-promoted to F₁. Link failure in cold region triggers O(log² n) update. Recalculation in 2ms.

### Key Differences from GRAPHSKEL

| Aspect | GRAPHSKEL | Network Routing |
|---|---|---|
| Purpose | Algorithm visualization | Practical routing system |
| Graph | Synthetic (Erdos-Renyi, road, social) | Real ISP topology |
| Queries | Arbitrary node pairs | Pre-defined city pairs |
| Failure model | Manual insertion/deletion | Poisson link failures |
| Metrics | Algorithm latency (ops/sec) | Convergence time, traffic loss |
| UI | Abstract 3D graph | Geographic map |

### Acceptance Criteria

- Convergence time: ≤ 10ms after link failure
- Traffic loss: ≤ 0.1% per failure event
- Path optimality: ≥ 95% of routes are top-2 shortest
- Throughput: ≥ 100 route queries/sec
- Availability: ≥ 99.9% uptime

---

## System Architecture

### High-Level Overview

```
┌──────────────────────────────────────────┐
│         Web Browser (React)               │
│    GRAPHSKEL (3D) + Network Routing App   │
└────────────────┬─────────────────────────┘
                 ↕ WebSocket / REST
┌──────────────────────────────────────────┐
│    FastAPI Backend (Python uvicorn)      │
│  /insert /delete /query /routing/* etc.  │
└────────────────┬─────────────────────────┘
                 ↕ Python
┌──────────────────────────────────────────┐
│      Algorithm Core (Python)              │
│  ADAPTSKEL + LCT + ETT + Heat + Delta-LDB│
│  Oracle: NetworkX (correctness check)    │
└──────────────────────────────────────────┘
```

### Backend Services

**FastAPI server** with routers:
- `routers/graph.py`: INSERT, DELETE, QUERY endpoints
- `routers/benchmark.py`: Benchmark job endpoints
- `routers/routing.py`: ISP routing endpoints

**Service modules:**
- `services/adaptskel_service.py`: Engine wrapper
- `services/benchmark_service.py`: Background benchmark jobs
- `services/routing_service.py`: ISP simulation

---

## Technical Requirements

### Tech Stack

**Backend:**
```
Python 3.11+
FastAPI 0.109+, uvicorn 0.27+
networkx 3.0+, numpy 1.21+, scipy 1.7+
pytest 7.0+, hypothesis 6.0+
```

**Frontend:**
```
React 18.2+, TypeScript
Three.js r160+, @react-three/fiber 8.16+
Recharts 2.10+, Tailwind 3.4+
Framer Motion 10.16+, Zustand 4.4+
```

**Database:**
```
PostgreSQL 15+ (for benchmark results, metrics)
```

---

## API Specification

### REST Endpoints

**POST /insert**
```json
Request:  {"u": 5, "v": 12, "weight": 3.5}
Response: {"edge_key": [5, 12], "layer": "F1", "cost_ms": 0.024}
```

**POST /delete**
```json
Request:  {"u": 5, "v": 12}
Response: {"edge_key": [5, 12], "replacement_found": true, "cost_ms": 0.031}
```

**POST /query**
```json
Request:  {"source": 5, "target": 12}
Response: {"distance": 7.5, "is_hot": true, "cost_ms": 0.002}
```

**POST /benchmark/run**
```json
Request:  {"graph_type": "road", "size": 5000, "workload": "zipf", "num_ops": 10000}
Response: {"job_id": "bench_abc123", "status": "queued"}
```

**GET /benchmark/results/:job_id**
```json
Response: {"status": "completed", "results": {"adaptskel": {...}, "dijkstra": {...}}}
```

**GET /routing/topology**
```json
Response: {"nodes": [...], "edges": [...]}
```

**POST /routing/route**
```json
Request:  {"source_city": "New York", "target_city": "Los Angeles"}
Response: {"path": [...], "latency_ms": 87, "convergence_time_ms": 2.1}
```

### WebSocket

**Endpoint:** `ws://localhost:8000/ws/stream`

**Server → Client:** JSON events (insert, delete, query, promotion, demotion, convergence)

---

## Performance Requirements

### Correctness

**Test 1: Correctness Oracle**
- Run ADAPTSKEL and NetworkX in parallel
- 100 trials × 10,000 random operations
- Assert: zero distance discrepancies
- Pass criterion: 100/100 trials pass

**Test 2: Property-Based**
- Triangle inequality: δ(u,w) ≤ δ(u,v) + δ(v,w)
- Symmetry: δ(u,v) = δ(v,u)
- Monotone insert/delete

### Throughput & Latency

**On n=100K, m=500K graph:**
- Insert: ≤5ms p95, ≤10ms p99
- Delete: ≤8ms p95, ≤15ms p99
- Hot query: ≤1ms p95, ≤2ms p99
- Cold query: ≤5ms p95, ≤10ms p99

**Single-threaded:** ≥100,000 mixed ops/sec

**Memory:** ≤1GB RAM for n=100K graph

### Speedup vs Dijkstra

- n=1K: ≥10×
- n=10K: ≥50×
- n=100K: ≥100×

### 3D Rendering

- ≥60 fps on n=1000 graph (Chrome, 2023 hardware)
- ≤5000 nodes before 30 fps

---

## Docker & Deployment

### Step 1: Create docker-compose.yml (Project Root)

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: adaptskel-backend
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=info
      - ENV=development
    volumes:
      - ./benchmarks/results:/app/benchmarks/results
      - ./core/python:/app/core/python
      - ./app/backend:/app/app/backend
    networks:
      - adaptskel-net
    depends_on:
      - db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 20s
    restart: unless-stopped

  frontend:
    build:
      context: ./app/frontend
      dockerfile: Dockerfile
    container_name: adaptskel-frontend
    ports:
      - "5173:5173"
    depends_on:
      backend:
        condition: service_healthy
    environment:
      - VITE_API_BASE=http://localhost:8000
      - VITE_WS_BASE=ws://localhost:8000
      - NODE_ENV=development
    volumes:
      - ./app/frontend/src:/app/src
      - ./app/frontend/public:/app/public
    networks:
      - adaptskel-net
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    container_name: adaptskel-db
    environment:
      - POSTGRES_USER=adaptskel
      - POSTGRES_PASSWORD=adaptskel_dev
      - POSTGRES_DB=adaptskel_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - adaptskel-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U adaptskel"]
      interval: 10s
      timeout: 5s
      retries: 5

networks:
  adaptskel-net:
    driver: bridge

volumes:
  postgres_data:
```

### Step 2: Create Dockerfile.backend (Project Root)

```dockerfile
FROM python:3.11-slim

LABEL maintainer="Pranav V."
LABEL description="ADAPTSKEL Backend - Fully Dynamic Graph SSSP Algorithm"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy requirements
COPY app/backend/requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    pip install --no-cache-dir uvicorn[standard] gunicorn

# Copy application code
COPY app/backend /app/app/backend
COPY core/python /app/core/python
COPY benchmarks /app/benchmarks
COPY tests /app/tests

# Create directories
RUN mkdir -p /app/benchmarks/results /app/logs

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=20s \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Production: use gunicorn
# Development: docker-compose overrides with uvicorn --reload
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app.backend.main:app"]
```

### Step 3: Create app/frontend/Dockerfile

```dockerfile
# Build stage
FROM node:20-alpine as builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Runtime stage
FROM node:20-alpine

WORKDIR /app

RUN npm install -g serve@14.2.0

COPY --from=builder /app/dist /app/dist
COPY --from=builder /app/public /app/public

RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

USER nextjs

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:5173 || exit 1

EXPOSE 5173

CMD ["serve", "-s", "dist", "-l", "5173", "-n"]
```

### Step 4: Quick Start

```bash
# Navigate to project root
cd /path/to/ADAPTSKEL-main

# Build and start all services (first run: 3-5 min)
docker-compose up --build

# Expected output:
# adaptskel-db-1       | PostgreSQL 15.0 is ready
# adaptskel-backend-1  | INFO:     Uvicorn running on http://0.0.0.0:8000
# adaptskel-frontend-1 | VITE v5.0.0 ready in 234 ms
# adaptskel-frontend-1 | ➜ Local: http://localhost:5173/

# Open browser: http://localhost:5173
```

### Step 5: Common Commands

```bash
# Stop all services (keep data)
docker-compose down

# Stop and delete all volumes (clean slate)
docker-compose down -v

# View status
docker-compose ps

# Follow backend logs
docker-compose logs -f backend

# Run correctness oracle test
docker-compose exec backend pytest tests/test_correctness.py -v

# Run all tests
docker-compose exec backend pytest tests/ -v

# Quick benchmark (2 min)
docker-compose exec backend python benchmarks/run_benchmarks.py --quick

# Full benchmark (30 min)
docker-compose exec backend python benchmarks/run_benchmarks.py --full

# Interactive Python shell
docker-compose exec backend python

# Bash shell in backend
docker-compose exec backend bash

# PostgreSQL CLI
docker-compose exec db psql -U adaptskel -d adaptskel_db

# Rebuild only backend (after Python changes)
docker-compose up --build backend

# Rebuild only frontend (after JS/TS changes)
docker-compose up --build frontend
```

### Production Deployment

**Create docker-compose.prod.yml:**

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=warning
      - ENV=production
    volumes:
      - ./benchmarks/results:/app/benchmarks/results
    networks:
      - adaptskel-net
    restart: always

  frontend:
    build:
      context: ./app/frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    environment:
      - NODE_ENV=production
    networks:
      - adaptskel-net
    restart: always

networks:
  adaptskel-net:
    driver: bridge
```

**Deploy production:**
```bash
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f backend
```

### Kubernetes Deployment

**Create k8s/backend-deployment.yaml:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: adaptskel-backend
  labels:
    app: adaptskel
    component: backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: adaptskel
      component: backend
  template:
    metadata:
      labels:
        app: adaptskel
        component: backend
    spec:
      containers:
      - name: backend
        image: adaptskel:backend-latest
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: LOG_LEVEL
          value: "info"
        - name: ENV
          value: "production"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: adaptskel-backend-service
spec:
  selector:
    app: adaptskel
    component: backend
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
```

**Deploy to Kubernetes:**
```bash
kubectl create namespace adaptskel
kubectl apply -f k8s/backend-deployment.yaml -n adaptskel
kubectl get pods -n adaptskel
kubectl logs -f deployment/adaptskel-backend -n adaptskel
kubectl scale deployment adaptskel-backend --replicas=5 -n adaptskel
```

### Troubleshooting

| Problem | Solution |
|---|---|
| Port 8000 already in use | `lsof -i :8000` to find process, then `docker-compose down -v` |
| Frontend can't connect | Check `VITE_API_BASE=http://localhost:8000` in docker-compose.yml |
| Database connection failed | `docker-compose exec db psql -U adaptskel -d adaptskel_db -c "SELECT 1"` |
| Out of disk space | `docker system prune -a --volumes` |
| Container stuck | `docker-compose kill && docker-compose rm -f && docker-compose up --build` |

---

## Implementation Roadmap

### Phase 1: Algorithm Core (Week 1-2)
- [ ] LCT implementation + unit tests
- [ ] ETT + Holm levels + unit tests
- [ ] Heat table + rolling window
- [ ] Delta-LDB queue
- [ ] Main ADAPTSKEL engine
- [ ] Correctness oracle tests (vs NetworkX)

### Phase 2: Benchmarks & Datasets (Week 3)
- [ ] Workload generators (Zipf, road, social, adversarial)
- [ ] Master benchmark runner
- [ ] Figure generation (matplotlib, paper-quality)

### Phase 3: Backend API (Week 4)
- [ ] FastAPI server scaffold
- [ ] Graph endpoints (/insert, /delete, /query)
- [ ] WebSocket streaming
- [ ] Benchmark endpoints
- [ ] Routing endpoints (ISP app)

### Phase 4: GRAPHSKEL Frontend (Week 5-6)
- [ ] React + Vite scaffold
- [ ] Three.js 3D renderer
- [ ] Mode 1: Live Streaming
- [ ] Mode 2: Skeleton Explorer
- [ ] Mode 3: Heat Heatmap
- [ ] Mode 4: Benchmark Arena
- [ ] Mode 5: Algorithm Explainer
- [ ] Mode 6: Network Routing App

### Phase 5: Documentation & Submission (Week 7-8)
- [ ] Algorithm proof
- [ ] Paper draft
- [ ] README + API docs
- [ ] Presentation slides
- [ ] Docker + deployment docs

---

## Testing Strategy

### Unit Tests
- `tests/test_lct.py`: Link-Cut Tree operations
- `tests/test_ett.py`: Euler Tour Tree with levels
- `tests/test_heat.py`: Heat table promotion/demotion
- `tests/test_delta_ldb.py`: Delta-LDB batching

### Integration Tests
- `tests/test_correctness.py`: Correctness oracle (ADAPTSKEL vs NetworkX)
- `tests/test_properties.py`: Property-based tests (Hypothesis)
  - Triangle inequality
  - Symmetry
  - Monotonicity (insert/delete)

### System Tests
- `tests/test_api.py`: REST endpoints + WebSocket
- E2E tests: Playwright/Cypress for frontend

### Performance Benchmarks
```bash
# Quick: n=1K, 1000 ops, 3 trials → 2 min
python benchmarks/run_benchmarks.py --quick

# Full: n=100K, 100K ops, 5 trials → 30 min
python benchmarks/run_benchmarks.py --full
```

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LCT implementation bugs → wrong distances | High | Critical | Test after each method, compare vs naive |
| ETT level-raising: O(log n) fails in practice | Medium | High | Empirically bound on all benchmarks |
| Stale flush scope: exceeds O(log² n) on dense graphs | Medium | High | Add scope limit + circuit breaker |
| Three.js memory leak → browser crash on large graphs | High | Medium | Dispose all geometries, monitor memory |
| WebSocket drops events under high load | Medium | Medium | Event queue with sequence numbers |
| Docker image too large / slow to build | Low | Medium | Use multi-stage builds, cache layers |

---

## Appendices

### A. Related Work

| Paper | Year | Result | Relation |
|---|---|---|---|
| Dijkstra | 1959 | O(E log V) static SSSP | Baseline |
| Sleator-Tarjan LCT | 1983 | O(log n) operations | F₁ data structure |
| Holm et al. ETT | 2001 | O(log² n) fully dynamic MST | F₂ level technique |
| Bernstein-Stein | 2016 | O(m log n/ε) decremental SSSP | Prior best fully dynamic |

### B. Parameter Tuning

```python
# Road network (Zipf α=1.3, sparse, n=100K)
adaptskel = AdaptSkel(
    T = ceil(log2(100000)) = 17,
    W = 100000,
    B = ceil(log2(100000)) = 17,
)

# Social graph (Zipf α=1.7, dense, n=10M)
adaptskel = AdaptSkel(
    T = ceil(log2(10000000)) = 24,
    W = 10000000 // 10 = 1000000,
    B = ceil(log2(10000000)) = 24,
)

# ISP backbone (Zipf α=1.2, moderate, n=200)
adaptskel = AdaptSkel(
    T = ceil(log2(200)) = 8,
    W = 200,
    B = ceil(log2(200)) = 8,
)
```

### C. Glossary

- **SSSP:** Single-Source Shortest Path
- **Fully dynamic:** Supports both insertions and deletions
- **Amortized:** Average cost per operation over sequence
- **Zipf distribution:** Power-law where k-th item has frequency ∝ 1/k^α
- **Skeleton F₁:** Hot edges in Link-Cut Tree
- **Residual F₂:** Cold edges in Euler Tour Tree
- **Heat score:** Query frequency per edge, decaying over window W
- **Delta-LDB:** Lazy Distance Label Batching (deferred propagation)

---

*ADAPTSKEL v2.0 — Comprehensive Edition*
*Complete technical specifications with Docker containerization*
*Authors: Pranav V. | Course: BT232AT | Institution: RV College of Engineering*
