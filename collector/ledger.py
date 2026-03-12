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

SAVED_SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS saved_sessions (
  session_id       VARCHAR PRIMARY KEY,
  name             VARCHAR NOT NULL,
  notes            TEXT,
  tags             VARCHAR,
  saved_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  event_count      INTEGER,
  agent_count      INTEGER,
  duration_seconds DOUBLE
);
CREATE INDEX IF NOT EXISTS idx_saved_at ON saved_sessions(saved_at);
"""


def _exec_ddl(conn: duckdb.DuckDBPyConnection, ddl: str):
    for stmt in ddl.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)


def init_db(path: str) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(path)
    _exec_ddl(conn, DDL)
    _exec_ddl(conn, SAVED_SESSIONS_DDL)
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
        SELECT e.session_id,
               MIN(e.received_at) AS first_event,
               MAX(e.received_at) AS last_event,
               MAX(e.cwd) AS cwd,
               CASE WHEN sv.session_id IS NOT NULL THEN true ELSE false END AS saved
        FROM events e
        LEFT JOIN saved_sessions sv ON e.session_id = sv.session_id
        WHERE e.session_id IS NOT NULL
        GROUP BY e.session_id, sv.session_id
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
               MAX(s.cwd) AS cwd,
               CASE WHEN sv.session_id IS NOT NULL THEN true ELSE false END AS saved
        FROM events s
        LEFT JOIN saved_sessions sv ON s.session_id = sv.session_id
        WHERE s.session_id IS NOT NULL
          AND s.session_id IN (
              SELECT session_id FROM events WHERE event_type = 'SessionStart'
          )
          AND s.session_id NOT IN (
              SELECT session_id FROM events WHERE event_type = 'SessionEnd'
          )
        GROUP BY s.session_id, sv.session_id
        ORDER BY first_event DESC
        """
    ).fetchall()
    columns = [desc[0] for desc in conn.description]
    return [dict(zip(columns, row)) for row in rows]


def save_session(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    name: str,
    notes: str | None = None,
    tags: str | None = None,
) -> dict:
    stats = conn.execute(
        """
        SELECT COUNT(*) AS event_count,
               COUNT(DISTINCT agent_id) AS agent_count,
               EXTRACT(EPOCH FROM (MAX(received_at) - MIN(received_at))) AS duration_seconds
        FROM events
        WHERE session_id = ?
        """,
        [session_id],
    ).fetchone()

    event_count, agent_count, duration_seconds = stats

    conn.execute(
        """
        INSERT INTO saved_sessions (session_id, name, notes, tags, event_count, agent_count, duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [session_id, name, notes, tags, event_count, agent_count, duration_seconds],
    )

    row = conn.execute(
        "SELECT * FROM saved_sessions WHERE session_id = ?", [session_id]
    ).fetchone()
    columns = [desc[0] for desc in conn.description]
    return dict(zip(columns, row))


def unsave_session(conn: duckdb.DuckDBPyConnection, session_id: str) -> bool:
    conn.execute("DELETE FROM saved_sessions WHERE session_id = ?", [session_id])
    return True


def get_saved_sessions(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM saved_sessions ORDER BY saved_at DESC"
    ).fetchall()
    columns = [desc[0] for desc in conn.description]
    return [dict(zip(columns, row)) for row in rows]


def update_saved_session(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    name: str | None = None,
    notes: str | None = None,
    tags: str | None = None,
) -> dict | None:
    existing = conn.execute(
        "SELECT * FROM saved_sessions WHERE session_id = ?", [session_id]
    ).fetchone()
    if not existing:
        return None

    columns = [desc[0] for desc in conn.description]
    current = dict(zip(columns, existing))

    updated_name = name if name is not None else current["name"]
    updated_notes = notes if notes is not None else current["notes"]
    updated_tags = tags if tags is not None else current["tags"]

    conn.execute(
        """
        UPDATE saved_sessions
        SET name = ?, notes = ?, tags = ?
        WHERE session_id = ?
        """,
        [updated_name, updated_notes, updated_tags, session_id],
    )

    row = conn.execute(
        "SELECT * FROM saved_sessions WHERE session_id = ?", [session_id]
    ).fetchone()
    columns = [desc[0] for desc in conn.description]
    return dict(zip(columns, row))
