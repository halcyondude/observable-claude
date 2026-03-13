#!/usr/bin/env python3
"""Seed DuckDB and LadybugDB with a deterministic test session.

Usage:
    python scripts/seed_test_data.py [--db-path ./data/duckdb/events.db] [--graph-path ./data/ladybug]
"""

import argparse
import os
import sys

# Allow running from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collector.ledger import init_db, write_event
from collector.graph import init_graph, materialize_event

# ---------------------------------------------------------------------------
# Deterministic identifiers
# ---------------------------------------------------------------------------
SESSION_ID = "test-session-00000000-0000-0000-0000-000000000001"
ORCHESTRATOR_ID = "agent-00000000-0000-0000-0000-000000000001"
CODE_WRITER_ID = "agent-00000000-0000-0000-0000-000000000002"
TEST_RUNNER_ID = "agent-00000000-0000-0000-0000-000000000003"
CWD = "/home/user/projects/observable-claude"

# Base timestamp: 2026-01-15T10:00:00Z — five-minute session
BASE_TS = "2026-01-15T10:00:00Z"


def _ts(offset_seconds: int) -> str:
    """Return an ISO timestamp offset from BASE_TS by the given seconds."""
    minutes, secs = divmod(offset_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"2026-01-15T10:{minutes:02d}:{secs:02d}Z"


def _tool_id(n: int) -> str:
    return f"tool-use-00000000-0000-0000-0000-{n:012d}"


def build_events() -> list[dict]:
    """Build the full deterministic event sequence."""
    events: list[dict] = []

    def _evt(event_type: str, ts: str, **kwargs) -> dict:
        e = {
            "event": {"event_type": event_type, "timestamp": ts},
            "session": {"session_id": SESSION_ID, "cwd": CWD},
        }
        # Merge extra fields into the right sub-dicts
        for k, v in kwargs.items():
            if k in ("agent_id", "agent_type"):
                e["session"][k] = v
            else:
                e["event"][k] = v
        return e

    # --- Session Start ---
    events.append(_evt("SessionStart", _ts(0)))

    # --- Orchestrator agent starts (spawned by session) ---
    events.append(_evt(
        "SubagentStart", _ts(1),
        agent_id=ORCHESTRATOR_ID, agent_type="orchestrator",
        depth=0, prompt="Implement feature X with tests",
    ))

    # --- Orchestrator: Read x3 ---
    for i, (path, offset) in enumerate([
        ("src/lib/stores/session.ts", 5),
        ("src/routes/+layout.svelte", 8),
        ("collector/graph.py", 12),
    ]):
        tid = _tool_id(i + 1)
        events.append(_evt(
            "PreToolUse", _ts(offset),
            agent_id=ORCHESTRATOR_ID, agent_type="orchestrator",
            tool_use_id=tid, tool_name="Read",
            tool_input={"file_path": f"{CWD}/{path}"},
        ))
        events.append(_evt(
            "PostToolUse", _ts(offset + 1),
            agent_id=ORCHESTRATOR_ID, agent_type="orchestrator",
            tool_use_id=tid, tool_name="Read",
            duration_ms=120 + i * 30,
            tool_response=f"Contents of {path} (42 lines)",
        ))

    # --- Orchestrator: Grep ---
    tid = _tool_id(4)
    events.append(_evt(
        "PreToolUse", _ts(18),
        agent_id=ORCHESTRATOR_ID, agent_type="orchestrator",
        tool_use_id=tid, tool_name="Grep",
        tool_input={"pattern": "materialize_event", "path": CWD, "type": "py"},
    ))
    events.append(_evt(
        "PostToolUse", _ts(19),
        agent_id=ORCHESTRATOR_ID, agent_type="orchestrator",
        tool_use_id=tid, tool_name="Grep",
        duration_ms=85,
        tool_response="collector/graph.py:61\ncollector/main.py:38",
    ))

    # --- Orchestrator spawns code-writer subagent ---
    tid_spawn1 = _tool_id(5)
    events.append(_evt(
        "PreToolUse", _ts(25),
        agent_id=ORCHESTRATOR_ID, agent_type="orchestrator",
        tool_use_id=tid_spawn1, tool_name="Agent",
        tool_input={"prompt": "Write the new component in src/lib/components/ToolPip.svelte"},
    ))
    events.append(_evt(
        "SubagentStart", _ts(26),
        agent_id=CODE_WRITER_ID, agent_type="code",
        parent_agent_id=ORCHESTRATOR_ID,
        depth=1, prompt="Write the new component in src/lib/components/ToolPip.svelte",
    ))

    # --- Code-writer: Write ---
    tid = _tool_id(6)
    events.append(_evt(
        "PreToolUse", _ts(30),
        agent_id=CODE_WRITER_ID, agent_type="code",
        tool_use_id=tid, tool_name="Write",
        tool_input={"file_path": f"{CWD}/src/lib/components/ToolPip.svelte", "content": "<script>...</script>"},
    ))
    events.append(_evt(
        "PostToolUse", _ts(31),
        agent_id=CODE_WRITER_ID, agent_type="code",
        tool_use_id=tid, tool_name="Write",
        duration_ms=95,
        tool_response="File written successfully",
    ))

    # --- Code-writer: Edit ---
    tid = _tool_id(7)
    events.append(_evt(
        "PreToolUse", _ts(35),
        agent_id=CODE_WRITER_ID, agent_type="code",
        tool_use_id=tid, tool_name="Edit",
        tool_input={"file_path": f"{CWD}/src/routes/tree/+page.svelte", "old_string": "<!-- pip -->", "new_string": "<ToolPip />"},
    ))
    events.append(_evt(
        "PostToolUse", _ts(36),
        agent_id=CODE_WRITER_ID, agent_type="code",
        tool_use_id=tid, tool_name="Edit",
        duration_ms=50,
        tool_response="File edited successfully",
    ))

    # --- Code-writer: Bash (build check) ---
    tid = _tool_id(8)
    events.append(_evt(
        "PreToolUse", _ts(40),
        agent_id=CODE_WRITER_ID, agent_type="code",
        tool_use_id=tid, tool_name="Bash",
        tool_input={"command": "cd dashboard && npm run build"},
    ))
    events.append(_evt(
        "PostToolUse", _ts(43),
        agent_id=CODE_WRITER_ID, agent_type="code",
        tool_use_id=tid, tool_name="Bash",
        duration_ms=3000,
        tool_response="vite v6.0.0 building for production...\n✓ built in 2.8s",
    ))

    # --- Code-writer stops ---
    events.append(_evt(
        "SubagentStop", _ts(45),
        agent_id=CODE_WRITER_ID, agent_type="code",
        status="complete",
    ))
    events.append(_evt(
        "PostToolUse", _ts(45),
        agent_id=ORCHESTRATOR_ID, agent_type="orchestrator",
        tool_use_id=tid_spawn1, tool_name="Agent",
        duration_ms=20000,
        tool_response="Component written and build verified",
    ))

    # --- Orchestrator spawns test-runner subagent ---
    tid_spawn2 = _tool_id(9)
    events.append(_evt(
        "PreToolUse", _ts(50),
        agent_id=ORCHESTRATOR_ID, agent_type="orchestrator",
        tool_use_id=tid_spawn2, tool_name="Agent",
        tool_input={"prompt": "Run the test suite and fix any failures"},
    ))
    events.append(_evt(
        "SubagentStart", _ts(51),
        agent_id=TEST_RUNNER_ID, agent_type="test",
        parent_agent_id=ORCHESTRATOR_ID,
        depth=1, prompt="Run the test suite and fix any failures",
    ))

    # --- Test-runner: Bash (run tests — fails) ---
    tid = _tool_id(10)
    events.append(_evt(
        "PreToolUse", _ts(55),
        agent_id=TEST_RUNNER_ID, agent_type="test",
        tool_use_id=tid, tool_name="Bash",
        tool_input={"command": "cd dashboard && npm test"},
    ))
    events.append(_evt(
        "PostToolUseFailure", _ts(58),
        agent_id=TEST_RUNNER_ID, agent_type="test",
        tool_use_id=tid, tool_name="Bash",
        duration_ms=2500,
        tool_response="FAIL src/lib/components/ToolPip.test.ts\nExpected 5 pips, received 0",
    ))

    # --- Test-runner: Bash (re-run tests — passes) ---
    tid = _tool_id(11)
    events.append(_evt(
        "PreToolUse", _ts(65),
        agent_id=TEST_RUNNER_ID, agent_type="test",
        tool_use_id=tid, tool_name="Bash",
        tool_input={"command": "cd dashboard && npm test"},
    ))
    events.append(_evt(
        "PostToolUse", _ts(68),
        agent_id=TEST_RUNNER_ID, agent_type="test",
        tool_use_id=tid, tool_name="Bash",
        duration_ms=2800,
        tool_response="PASS src/lib/components/ToolPip.test.ts\n5 tests passed",
    ))

    # --- Test-runner: mcp__ladybug-observer__query ---
    tid = _tool_id(12)
    events.append(_evt(
        "PreToolUse", _ts(72),
        agent_id=TEST_RUNNER_ID, agent_type="test",
        tool_use_id=tid, tool_name="mcp__ladybug-observer__query",
        tool_input={"query": "MATCH (a:Agent)-[r:INVOKED]->(t:Tool) RETURN t.name, count(r) ORDER BY count(r) DESC"},
    ))
    events.append(_evt(
        "PostToolUse", _ts(73),
        agent_id=TEST_RUNNER_ID, agent_type="test",
        tool_use_id=tid, tool_name="mcp__ladybug-observer__query",
        duration_ms=150,
        tool_response='[{"t.name": "Bash", "count(r)": 3}, {"t.name": "Read", "count(r)": 3}]',
    ))

    # --- Test-runner stops ---
    events.append(_evt(
        "SubagentStop", _ts(78),
        agent_id=TEST_RUNNER_ID, agent_type="test",
        status="complete",
    ))
    events.append(_evt(
        "PostToolUse", _ts(78),
        agent_id=ORCHESTRATOR_ID, agent_type="orchestrator",
        tool_use_id=tid_spawn2, tool_name="Agent",
        duration_ms=28000,
        tool_response="Tests fixed and passing",
    ))

    # --- Orchestrator stops ---
    events.append(_evt(
        "SubagentStop", _ts(82),
        agent_id=ORCHESTRATOR_ID, agent_type="orchestrator",
        status="complete",
    ))

    # --- Session End ---
    events.append(_evt("SessionEnd", _ts(85)))

    return events


def seed(db_path: str, graph_path: str) -> None:
    """Write all events to DuckDB and materialize into LadybugDB."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    os.makedirs(graph_path, exist_ok=True)

    conn = init_db(db_path)
    db, gconn = init_graph(graph_path)

    events = build_events()
    print(f"Seeding {len(events)} events into {db_path}")

    for event in events:
        write_event(conn, event)
        materialize_event(gconn, event)

    conn.close()

    # Verify
    verify_conn = init_db(db_path)
    count = verify_conn.execute(
        "SELECT count(*) FROM events WHERE session_id = ?", [SESSION_ID]
    ).fetchone()[0]
    verify_conn.close()

    print(f"Verified: {count} events in DuckDB for session {SESSION_ID}")
    print(f"Graph materialized at {graph_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed test data for CC Observer")
    parser.add_argument(
        "--db-path",
        default="./data/duckdb/events.db",
        help="Path to DuckDB database file (default: ./data/duckdb/events.db)",
    )
    parser.add_argument(
        "--graph-path",
        default="./data/ladybug",
        help="Path to LadybugDB directory (default: ./data/ladybug)",
    )
    args = parser.parse_args()
    seed(args.db_path, args.graph_path)


if __name__ == "__main__":
    main()
