import uuid
import json
import duckdb


DDL = """
CREATE TABLE IF NOT EXISTS events (
  event_id    VARCHAR PRIMARY KEY,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  event_type  VARCHAR NOT NULL,
  session_id  VARCHAR,
  agent_id    VARCHAR,
  agent_type  VARCHAR,
  tool_use_id VARCHAR,
  tool_name   VARCHAR,
  cwd         VARCHAR,
  payload     JSON
);
CREATE INDEX IF NOT EXISTS idx_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_pair ON events(tool_use_id);
CREATE INDEX IF NOT EXISTS idx_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_time ON events(received_at);
CREATE INDEX IF NOT EXISTS idx_cwd ON events(cwd);
"""


def init_db(path: str) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(path)
    for stmt in DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    return conn


def write_event(conn: duckdb.DuckDBPyConnection, event: dict) -> str:
    event_id = str(uuid.uuid4())
    event_type = event.get("event", {}).get("event_type", event.get("event_type", "unknown"))
    session_id = event.get("session", {}).get("session_id", event.get("session_id"))
    agent_id = event.get("session", {}).get("agent_id", event.get("agent_id"))
    agent_type = event.get("session", {}).get("agent_type", event.get("agent_type"))
    tool_use_id = event.get("event", {}).get("tool_use_id", event.get("tool_use_id"))
    tool_name = event.get("event", {}).get("tool_name", event.get("tool_name"))
    cwd = event.get("session", {}).get("cwd", event.get("cwd"))
    payload = json.dumps(event)

    conn.execute(
        """
        INSERT INTO events (event_id, event_type, session_id, agent_id, agent_type, tool_use_id, tool_name, cwd, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [event_id, event_type, session_id, agent_id, agent_type, tool_use_id, tool_name, cwd, payload],
    )
    return event_id


def query_events(
    conn: duckdb.DuckDBPyConnection,
    filters: dict | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    filters = filters or {}
    clauses = []
    params = []

    for col in ("event_type", "session_id", "agent_id", "tool_use_id"):
        if col in filters and filters[col] is not None:
            clauses.append(f"{col} = ?")
            params.append(filters[col])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])

    rows = conn.execute(
        f"SELECT * FROM events {where} ORDER BY received_at DESC LIMIT ? OFFSET ?",
        params,
    ).fetchall()

    columns = [desc[0] for desc in conn.description]
    return [dict(zip(columns, row)) for row in rows]


def get_sessions(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT session_id,
               MIN(received_at) AS first_event,
               MAX(received_at) AS last_event,
               MAX(cwd) AS cwd
        FROM events
        WHERE session_id IS NOT NULL
        GROUP BY session_id
        ORDER BY first_event DESC
        """
    ).fetchall()
    columns = [desc[0] for desc in conn.description]
    return [dict(zip(columns, row)) for row in rows]


def get_grouped_sessions(
    conn: duckdb.DuckDBPyConnection,
    since: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return sessions grouped by workspace (cwd) with aggregate stats."""
    params = []
    where_clauses = ["session_id IS NOT NULL", "cwd IS NOT NULL"]

    if since:
        where_clauses.append("received_at >= ?::TIMESTAMPTZ")
        params.append(since)

    where = " AND ".join(where_clauses)

    # Get ended session IDs for status detection
    ended_rows = conn.execute(
        "SELECT DISTINCT session_id FROM events WHERE event_type = 'SessionEnd'"
    ).fetchall()
    ended_sessions = {row[0] for row in ended_rows}

    # Get session-level aggregates
    limit_clause = f"LIMIT {int(limit)}" if limit else ""
    rows = conn.execute(
        f"""
        SELECT session_id,
               MAX(cwd) AS cwd,
               MIN(received_at) AS start_ts,
               MAX(received_at) AS end_ts,
               COUNT(*) AS event_count,
               COUNT(DISTINCT agent_id) FILTER (WHERE agent_id IS NOT NULL) AS agent_count
        FROM events
        WHERE {where}
        GROUP BY session_id
        ORDER BY start_ts DESC
        """,
        params,
    ).fetchall()

    # Group by cwd
    workspace_map: dict[str, dict] = {}
    for row in rows:
        session_id, cwd, start_ts, end_ts, event_count, agent_count = row
        is_active = session_id not in ended_sessions

        session = {
            "session_id": session_id,
            "cwd": cwd,
            "branch": "",
            "start_ts": start_ts.isoformat() if hasattr(start_ts, "isoformat") else str(start_ts),
            "end_ts": end_ts.isoformat() if hasattr(end_ts, "isoformat") else str(end_ts),
            "status": "active" if is_active else "complete",
            "event_count": event_count,
            "agent_count": agent_count,
        }

        if cwd not in workspace_map:
            name = cwd.rstrip("/").rsplit("/", 1)[-1] if "/" in cwd else cwd
            workspace_map[cwd] = {
                "workspace": {"path": cwd, "name": name},
                "sessions": [],
            }
        workspace_map[cwd]["sessions"].append(session)

    # Apply per-workspace limit if specified
    result = list(workspace_map.values())
    if limit:
        for group in result:
            group["sessions"] = group["sessions"][:limit]

    return result


def get_active_sessions(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT s.session_id,
               MIN(s.received_at) AS first_event,
               MAX(s.received_at) AS last_event,
               MAX(s.cwd) AS cwd
        FROM events s
        WHERE s.session_id IS NOT NULL
          AND s.session_id IN (
              SELECT session_id FROM events WHERE event_type = 'SessionStart'
          )
          AND s.session_id NOT IN (
              SELECT session_id FROM events WHERE event_type = 'SessionEnd'
          )
        GROUP BY s.session_id
        ORDER BY first_event DESC
        """
    ).fetchall()
    columns = [desc[0] for desc in conn.description]
    return [dict(zip(columns, row)) for row in rows]
