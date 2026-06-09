# ADAPTSKEL — Product Requirements Document v2.0
## MINIMAL EDITION — Quick Reference with Docker Setup

**Version:** 2.0-Minimal | **Date:** June 2026 | **Status:** Active Development

---

## Executive Summary

**ADAPTSKEL** maintains exact shortest paths in fully dynamic graphs (continuous edge insertions/deletions) in O(log² n) amortized update time and O(log n) hot-path queries under Zipf-distributed workloads.

**Three deliverables:**
1. GRAPHSKEL — 6-mode interactive 3D demo
2. Network Routing App — ISP backbone routing with real-time link failures (NEW)
3. Docker containerization — production-ready deployment

---

## Problem & Solution

**Problem:** Graphs change constantly (5,000-50,000 changes/sec in production). Rerunning Dijkstra per change is impossible: O(E log V) per update. No algorithm achieves exact distances + fully dynamic + polylogarithmic simultaneously.

**Solution:** Leverage Zipf-distributed query workloads. Real graphs have natural hot/cold edge structure. Maintain hot edges in fast Link-Cut Tree (F₁), handle cold edges lazily in Euler Tour Tree (F₂).

**Performance:**

| Algorithm | Insert | Delete | Query | Exact? | Dynamic? |
|---|---|---|---|---|---|
| Dijkstra | O(E log V) | O(E log V) | O(1) | ✓ | ✓ |
| Link-Cut Tree | O(log n) | O(log n) | O(log n) | ✗ | ✓ |
| **ADAPTSKEL** | **O(log² n)** | **O(log² n)** | **O(log n) hot** | **✓** | **✓** |

---

## Algorithm Core

### Data Structures

**F₁ (Skeleton, Link-Cut Tree):**
- Hot edges (heat ≥ T)
- O(log n) queries, link, cut

**F₂ (Residual, Euler Tour Tree):**
- Cold edges (heat < T)
- O(log² n) replacement-edge finding

**Heat Table:**
- Rolling window W tracks last W queries
- Promotion: heat ≥ T → move to F₁
- Demotion: heat ≤ T/2 → move to F₂

**Delta-LDB:**
- Deferred distance propagation
- O(log² n) amortized cost

### Complexity

- **INSERT:** O(log² n) amortized
- **DELETE:** O(log² n) amortized
- **QUERY (hot):** O(log n) amortized (most queries)
- **QUERY (cold):** O(log² n) amortized (rare, Zipf-bounded)
- **Space:** O(m + n log n)

---

## GRAPHSKEL Demo (6 Modes)

1. **Live Streaming:** ADAPTSKEL vs Dijkstra side-by-side
2. **Skeleton Explorer:** Toggle F₁/F₂, inspect heat scores
3. **Heat Heatmap:** Watch Zipf distribution crystallize
4. **Benchmark Arena:** Performance bars, latency charts
5. **Algorithm Explainer:** Step-through with narration
6. **Network Routing App:** ISP backbone with map UI (NEW)

---

## Network Routing Application (NEW)

Real ISP backbone routing system demonstrating practical ADAPTSKEL value.

**Features:**
- 50-200 cities connected by fiber links
- Real-time link failure simulation (Poisson schedule)
- Route queries on city pairs
- Geographic map visualization
- Metrics: convergence ≤10ms, traffic loss ≤0.1%, optimality ≥95%

**Why different from GRAPHSKEL:**
- Practical routing system (not visualization)
- Fixed queries (city pairs, not arbitrary nodes)
- Realistic failure model (Poisson, not manual)
- Measures routing convergence (not algorithm latency)

---

## Tech Stack

**Backend:** Python 3.11+, FastAPI, uvicorn, PostgreSQL
**Frontend:** React 18, Three.js, Recharts, Tailwind CSS
**Testing:** pytest, hypothesis, NetworkX
**Deployment:** Docker, Docker Compose, Kubernetes (optional)

---

## API Specification

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/insert` | Insert edge (u, v, weight) |
| POST | `/delete` | Delete edge (u, v) |
| POST | `/query` | Query shortest path (source, target) |
| GET | `/health` | Health check |
| POST | `/benchmark/run` | Start benchmark job |
| GET | `/benchmark/results/:id` | Get results |
| GET | `/routing/topology` | Fetch ISP topology |
| POST | `/routing/route` | Compute route (city pair) |
| POST | `/routing/simulate_failure` | Simulate link failure |

**WebSocket:** `ws://localhost:8000/ws/stream` (live graph events)

---

## Performance Requirements

### Correctness
- 100 trials × 10,000 random ops each
- Zero distance discrepancies vs NetworkX oracle

### Throughput
- **Single-threaded:** ≥100,000 mixed ops/sec on n=100K graph
- **Insert:** ≤10ms p99
- **Delete:** ≤15ms p99
- **Hot query:** ≤2ms p99
- **Cold query:** ≤10ms p99

### Speedup vs Dijkstra
- n=1K: ≥10×
- n=10K: ≥50×
- n=100K: ≥100×

### Memory
- ≤1GB RAM for n=100K, m=500K graph

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

  frontend:
    build:
      context: ./app/frontend
      dockerfile: Dockerfile
    container_name: adaptskel-frontend
    ports:
      - "5173:5173"
    depends_on:
      - backend
    environment:
      - VITE_API_BASE=http://localhost:8000
      - NODE_ENV=development
    volumes:
      - ./app/frontend/src:/app/src
    networks:
      - adaptskel-net

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

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl libpq-dev && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY app/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir uvicorn[standard] gunicorn

COPY app/backend app/backend
COPY core/python core/python
COPY benchmarks benchmarks

ENV PYTHONPATH=/app:$PYTHONPATH

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", "app.backend.main:app"]
```

### Step 3: Create app/frontend/Dockerfile

```dockerfile
FROM node:20-alpine as builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine

WORKDIR /app
RUN npm install -g serve

COPY --from=builder /app/dist dist

EXPOSE 5173

CMD ["serve", "-s", "dist", "-l", "5173"]
```

### Step 4: Start Everything

```bash
cd /path/to/ADAPTSKEL-main

# Build and start (first run: 3-5 min)
docker-compose up --build

# Expected output:
# adaptskel-backend-1  | INFO:     Uvicorn running on http://0.0.0.0:8000
# adaptskel-frontend-1 | VITE v5.0.0 ready in 234 ms
# adaptskel-frontend-1 | ➜ Local: http://localhost:5173/

# Open: http://localhost:5173
```

### Common Commands

```bash
# Stop (keep data)
docker-compose down

# Stop (delete all data)
docker-compose down -v

# Status
docker-compose ps

# View logs
docker-compose logs -f backend

# Run tests
docker-compose exec backend pytest tests/ -v

# Run quick benchmark
docker-compose exec backend python benchmarks/run_benchmarks.py --quick

# Interactive shell
docker-compose exec backend bash

# Rebuild backend
docker-compose up --build backend

# Rebuild frontend
docker-compose up --build frontend
```

### Production Deployment

**docker-compose.prod.yml:**

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
      - ENV=production
      - LOG_LEVEL=warning
    restart: always

  frontend:
    build:
      context: ./app/frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    environment:
      - NODE_ENV=production
    restart: always

networks:
  adaptskel-net:
    driver: bridge
```

**Deploy:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes (Optional)

**k8s/backend-deployment.yaml:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: adaptskel-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: adaptskel-backend
  template:
    metadata:
      labels:
        app: adaptskel-backend
    spec:
      containers:
      - name: backend
        image: adaptskel:backend-latest
        ports:
        - containerPort: 8000
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
---
apiVersion: v1
kind: Service
metadata:
  name: adaptskel-backend-service
spec:
  selector:
    app: adaptskel-backend
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 8000
```

**Deploy:**
```bash
kubectl create namespace adaptskel
kubectl apply -f k8s/backend-deployment.yaml -n adaptskel
kubectl get pods -n adaptskel
```

### Troubleshooting

| Problem | Solution |
|---|---|
| Port 8000 in use | `docker-compose down -v && docker system prune -a` |
| Frontend can't connect | Check `VITE_API_BASE=http://localhost:8000` |
| DB connection failed | `docker-compose exec db psql -U adaptskel -d adaptskel_db -c "SELECT 1"` |
| Out of disk | `docker system prune -a --volumes` |
| Container stuck | `docker-compose kill && docker-compose rm -f && docker-compose up --build` |

---

## Testing Strategy

### Unit Tests
- LCT operations: `tests/test_lct.py`
- ETT with levels: `tests/test_ett.py`
- Heat table: `tests/test_heat.py`
- Delta-LDB: `tests/test_delta_ldb.py`

### Integration Tests
- Correctness oracle (ADAPTSKEL vs NetworkX): `tests/test_correctness.py`
- Property-based tests: `tests/test_properties.py`

### System Tests
- API endpoints: `tests/test_api.py`
- E2E: Playwright/Cypress

### Performance
```bash
# Quick: 2 minutes
docker-compose exec backend python benchmarks/run_benchmarks.py --quick

# Full: 30 minutes
docker-compose exec backend python benchmarks/run_benchmarks.py --full
```

---

## Implementation Roadmap

**Week 1-2:** Algorithm (LCT, ETT, Heat, Delta-LDB, tests)
**Week 3:** Benchmarks (generators, figures)
**Week 4:** Backend API (FastAPI, endpoints)
**Week 5-6:** Frontend (React, Three.js, 6 modes)
**Week 7-8:** Docs, paper, slides

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LCT bugs | High | Critical | Test vs naive implementation |
| ETT level-raising fails | Medium | High | Empirical bounds on benchmarks |
| Three.js memory leak | High | Medium | Dispose geometries, monitor |
| WebSocket event loss | Medium | Medium | Event queue + sequence numbers |
| Docker image too large | Low | Medium | Multi-stage builds |

---

## Appendix: Configuration

**Self-tuning parameters:**

```python
T = ceil(log2(n))        # Promotion threshold
W = n                     # Heat window
B = ceil(log2(n))        # Decrease batch size
```

**Examples:**

| System | n | T | W | B |
|---|---|---|---|---|
| Road network | 100K | 17 | 100K | 17 |
| Social graph | 10M | 24 | 1M | 24 |
| ISP backbone | 200 | 8 | 200 | 8 |

---

*ADAPTSKEL v2.0 — Minimal Edition*
*Quick reference with all essential details and Docker setup*
*Authors: Pranav V. | Course: BT232AT | Institution: RV College of Engineering*
