#!/usr/bin/env python3
"""Rebuild LadybugDB graph from DuckDB event ledger.

Usage:
    python scripts/replay.py
    python -m scripts.replay

Environment variables:
    DUCKDB_PATH  — path to DuckDB file (default: ./data/duckdb/events.db)
    KUZU_PATH    — path to LadybugDB directory (default: ./data/kuzu)
"""

import json
import logging
import os
import sys
import time

import duckdb

# Allow running as both `python scripts/replay.py` and `python -m scripts.replay`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collector.graph import init_graph, reset_graph, materialize_event

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def replay(duckdb_path: str, kuzu_path: str) -> None:
    logger.info("Connecting to DuckDB at %s", duckdb_path)
    duck = duckdb.connect(duckdb_path, read_only=True)

    total = duck.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    logger.info("Found %d events to replay", total)

    logger.info("Initializing LadybugDB at %s", kuzu_path)
    os.makedirs(kuzu_path, exist_ok=True)
    _db, conn = init_graph(kuzu_path)

    logger.info("Resetting graph tables (clean slate)")
    reset_graph(conn)

    rows = duck.execute(
        "SELECT payload FROM events ORDER BY received_at ASC"
    ).fetchall()

    replayed = 0
    errors = 0
    start = time.time()

    for i, (payload_json,) in enumerate(rows, 1):
        event = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
        try:
            materialize_event(conn, event)
            replayed += 1
        except Exception:
            logger.exception("Failed to replay event %d", i)
            errors += 1

        if i % 100 == 0 or i == total:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed > 0 else 0
            logger.info("Progress: %d/%d events (%.0f events/s), %d errors", i, total, rate, errors)

    elapsed = time.time() - start
    logger.info(
        "Replay complete: %d events replayed, %d errors, %.1fs elapsed",
        replayed, errors, elapsed,
    )

    duck.close()


def main() -> None:
    duckdb_path = os.environ.get("DUCKDB_PATH", "./data/duckdb/events.db")
    kuzu_path = os.environ.get("KUZU_PATH", "./data/kuzu")

    if not os.path.exists(duckdb_path):
        logger.error("DuckDB file not found at %s", duckdb_path)
        sys.exit(1)

    replay(duckdb_path, kuzu_path)


if __name__ == "__main__":
    main()
