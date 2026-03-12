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


def get_session_events(conn: duckdb.DuckDBPyConnection, session_id: str) -> list[dict]:
    """Return all events for a session ordered chronologically (ASC)."""
    rows = conn.execute(
        """
        SELECT * FROM events
        WHERE session_id = ?
        ORDER BY received_at ASC
        """,
        [session_id],
    ).fetchall()
    columns = [desc[0] for desc in conn.description]
    return [dict(zip(columns, row)) for row in rows]


def get_session_event_count(conn: duckdb.DuckDBPyConnection, session_id: str) -> int:
    """Return the total number of events for a session."""
    result = conn.execute(
        "SELECT COUNT(*) FROM events WHERE session_id = ?",
        [session_id],
    ).fetchone()
    return result[0] if result else 0


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
