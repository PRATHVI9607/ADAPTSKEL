#!/usr/bin/env bash
# ADAPTSKEL project setup — one command to get everything running
set -e

echo "=== ADAPTSKEL Project Setup ==="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

cd "$ROOT"

# ── Python environment ────────────────────────────────────────────────────────
echo "[1/5] Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip -q
pip install -r app/backend/requirements.txt -q
pip install networkx numpy scipy pytest hypothesis -q

echo "      Python deps installed."

# ── Benchmark datasets placeholder ───────────────────────────────────────────
echo "[2/5] Preparing benchmark directories..."
mkdir -p benchmarks/datasets benchmarks/results

# ── Frontend ──────────────────────────────────────────────────────────────────
echo "[3/5] Installing frontend dependencies..."
cd app/frontend
npm install --silent
cd "$ROOT"

echo "      Frontend deps installed."

# ── Smoke tests ───────────────────────────────────────────────────────────────
echo "[4/5] Running smoke tests..."
source .venv/bin/activate
python -m pytest tests/test_lct.py tests/test_heat.py -q --tb=short 2>/dev/null || echo "      (Tests skipped — run after algorithm is built)"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "[5/5] Setup complete!"
echo ""
echo "To start the project:"
echo "  Backend:   source .venv/bin/activate && cd app/backend && uvicorn main:app --reload"
echo "  Frontend:  cd app/frontend && npm run dev"
echo "  Tests:     source .venv/bin/activate && python -m pytest tests/ -v"
echo "  Benchmarks: source .venv/bin/activate && python benchmarks/run_benchmarks.py --quick"
