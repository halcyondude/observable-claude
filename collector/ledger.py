import uuid
import json
import hashlib
from datetime import datetime, timezone

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

CREATE TABLE IF NOT EXISTS messages (
  message_id    VARCHAR PRIMARY KEY,
  event_id      VARCHAR,
  session_id    VARCHAR NOT NULL,
  agent_id      VARCHAR NOT NULL,
  role          VARCHAR NOT NULL,
  sequence      INTEGER NOT NULL,
  timestamp     TIMESTAMPTZ NOT NULL,
  content       TEXT,
  content_hash  VARCHAR,
  content_bytes INTEGER,
  synthetic     BOOLEAN DEFAULT FALSE,
  metadata      JSON
);
CREATE INDEX IF NOT EXISTS idx_msg_agent ON messages(agent_id);
CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_msg_role ON messages(role);
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


# --- Messages ---


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_next_sequence(conn: duckdb.DuckDBPyConnection, agent_id: str) -> int:
    """Return the next sequence number for a given agent's messages."""
    row = conn.execute(
        "SELECT COALESCE(MAX(sequence), -1) FROM messages WHERE agent_id = ?",
        [agent_id],
    ).fetchone()
    return row[0] + 1 if row else 0


def write_message(
    conn: duckdb.DuckDBPyConnection,
    *,
    session_id: str,
    agent_id: str,
    role: str,
    content: str,
    event_id: str | None = None,
    sequence: int | None = None,
    synthetic: bool = False,
    metadata: dict | None = None,
) -> str:
    """Write a message to the messages table. Returns the message_id."""
    message_id = str(uuid.uuid4())
    if sequence is None:
        sequence = get_next_sequence(conn, agent_id)
    ts = datetime.now(timezone.utc)
    content_h = _content_hash(content) if content else None
    content_bytes = len(content.encode("utf-8")) if content else 0
    meta_json = json.dumps(metadata) if metadata else None

    conn.execute(
        """
        INSERT INTO messages
            (message_id, event_id, session_id, agent_id, role, sequence, timestamp,
             content, content_hash, content_bytes, synthetic, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            message_id, event_id, session_id, agent_id, role, sequence, ts,
            content, content_h, content_bytes, synthetic, meta_json,
        ],
    )
    return message_id


def get_agent_messages(
    conn: duckdb.DuckDBPyConnection,
    agent_id: str,
) -> list[dict]:
    """Return all messages for an agent, ordered by sequence."""
    rows = conn.execute(
        "SELECT * FROM messages WHERE agent_id = ? ORDER BY sequence ASC",
        [agent_id],
    ).fetchall()
    columns = [desc[0] for desc in conn.description]
    return [dict(zip(columns, row)) for row in rows]


def get_session_messages(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
) -> list[dict]:
    """Return all messages for a session, ordered by agent and sequence."""
    rows = conn.execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY agent_id, sequence ASC",
        [session_id],
    ).fetchall()
    columns = [desc[0] for desc in conn.description]
    return [dict(zip(columns, row)) for row in rows]


def get_agent_tool_summary(
    conn: duckdb.DuckDBPyConnection,
    agent_id: str,
) -> dict:
    """Summarize tool calls for an agent from the events table."""
    rows = conn.execute(
        """
        SELECT tool_name,
               COUNT(*) as call_count,
               SUM(CASE WHEN event_type = 'PostToolUse' THEN 1 ELSE 0 END) as success_count,
               SUM(CASE WHEN event_type = 'PostToolUseFailure' THEN 1 ELSE 0 END) as fail_count
        FROM events
        WHERE agent_id = ? AND event_type IN ('PostToolUse', 'PostToolUseFailure')
        GROUP BY tool_name
        """,
        [agent_id],
    ).fetchall()
    total = sum(r[1] for r in rows)
    tools = [r[0] for r in rows if r[0]]
    successes = sum(r[2] for r in rows)
    failures = sum(r[3] for r in rows)
    return {
        "total": total,
        "tools": tools,
        "successes": successes,
        "failures": failures,
    }
