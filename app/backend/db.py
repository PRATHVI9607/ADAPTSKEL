"""
PostgreSQL database connection utility.
Provides logging of benchmark runs and routing simulation metrics.
Fail-safe: falls back to warnings if database is unavailable.
"""
from __future__ import annotations

import json
import os

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    _HAS_PSYCOPG2 = True
except ImportError as e:
    # psycopg2 isn't installed in this environment (e.g. local dev venv without
    # the routing-app's requirements, or a minimal test container). Degrade to
    # transient (no-DB) mode instead of crashing every module that imports us —
    # this is what "fail-safe" in the module docstring is actually supposed to mean.
    psycopg2 = None  # type: ignore[assignment]
    _HAS_PSYCOPG2 = False
    print(f"[DB WARN] psycopg2 not installed, running in transient mode. Error: {e}")

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://adaptskel:adaptskel_dev@db:5432/adaptskel_db"
)

def get_connection():
    """Establish and return a connection to PostgreSQL, or None if unavailable."""
    if not _HAS_PSYCOPG2:
        return None
    try:
        conn = psycopg2.connect(DB_URL, connect_timeout=3)
        return conn
    except Exception as e:
        # Silently log/warn but do not crash the application
        print(f"[DB WARN] Database unavailable, running in transient mode. Error: {e}")
        return None

def init_db():
    """Initialise database tables for logging benchmark runs and metrics."""
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id VARCHAR(64) PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    graph_type VARCHAR(32),
                    node_count INTEGER,
                    operations INTEGER,
                    zipf_alpha DOUBLE PRECISION,
                    results JSONB
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS routing_simulations (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    event_type VARCHAR(16), -- 'failure' | 'recovery' | 'query'
                    edge_u INTEGER,
                    edge_v INTEGER,
                    latency_us DOUBLE PRECISION,
                    active_failures INTEGER,
                    optimality DOUBLE PRECISION
                );
            """)
            conn.commit()
            print("[DB INFO] Database tables initialised successfully.")
    except Exception as e:
        print(f"[DB ERROR] Initialisation failed: {e}")
        conn.rollback()
    finally:
        conn.close()

def save_benchmark_run(run_id: str, config: dict, results: dict):
    """Save a completed benchmark run's details and results."""
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO benchmark_runs (id, graph_type, node_count, operations, zipf_alpha, results)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    run_id,
                    config.get("graph_type"),
                    config.get("node_count"),
                    config.get("operations"),
                    config.get("zipf_alpha"),
                    json.dumps(results)
                )
            )
            conn.commit()
            print(f"[DB INFO] Saved benchmark run {run_id} to database.")
    except Exception as e:
        print(f"[DB ERROR] Save benchmark run failed: {e}")
        conn.rollback()
    finally:
        conn.close()

def log_routing_event(event_type: str, u: int, v: int, latency_us: float, active_failures: int, optimality: float = 100.0):
    """Log an ISP routing simulation failure, recovery, or query event."""
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO routing_simulations (event_type, edge_u, edge_v, latency_us, active_failures, optimality)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (event_type, u, v, latency_us, active_failures, optimality)
            )
            conn.commit()
    except Exception as e:
        print(f"[DB ERROR] Logging routing event failed: {e}")
        conn.rollback()
    finally:
        conn.close()
