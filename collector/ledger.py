import hashlib
import re
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
CREATE TABLE IF NOT EXISTS messages (
  message_id    VARCHAR PRIMARY KEY,
  event_id      VARCHAR,
  session_id    VARCHAR NOT NULL,
  agent_id      VARCHAR NOT NULL,
  role          VARCHAR NOT NULL,
  sequence      INTEGER NOT NULL,
  timestamp     TIMESTAMPTZ NOT NULL DEFAULT now(),
  content       TEXT,
  content_hash  VARCHAR,
  content_bytes INTEGER,
  metadata      JSON
);
CREATE INDEX IF NOT EXISTS idx_msg_agent ON messages(agent_id);
CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_msg_role ON messages(role);
CREATE INDEX IF NOT EXISTS idx_msg_hash ON messages(content_hash);
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


def write_message(
    conn: duckdb.DuckDBPyConnection,
    *,
    event_id: str | None,
    session_id: str,
    agent_id: str,
    role: str,
    sequence: int,
    content: str | None,
    metadata: dict | None = None,
) -> str:
    """Write a message to the messages table. Returns the message_id."""
    message_id = str(uuid.uuid4())
    content_hash = hashlib.sha256(content.encode()).hexdigest() if content else None
    content_bytes = len(content.encode()) if content else 0

    conn.execute(
        """
        INSERT INTO messages (message_id, event_id, session_id, agent_id, role, sequence, content, content_hash, content_bytes, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            message_id,
            event_id,
            session_id,
            agent_id,
            role,
            sequence,
            content,
            content_hash,
            content_bytes,
            json.dumps(metadata) if metadata else None,
        ],
    )
    return message_id


def _build_snippet(content: str, query: str, context_chars: int = 50) -> str | None:
    """Build a snippet showing the match in context with **bold** markers."""
    if not content or not query:
        return None
    try:
        match = re.search(query, content, re.IGNORECASE)
    except re.error:
        # Fall back to literal substring search
        idx = content.lower().find(query.lower())
        if idx == -1:
            return None
        match_text = content[idx : idx + len(query)]
        start = max(0, idx - context_chars)
        end = min(len(content), idx + len(query) + context_chars)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""
        before = content[start:idx]
        after = content[idx + len(query) : end]
        return f"{prefix}{before}**{match_text}**{after}{suffix}"

    if not match:
        return None

    start = max(0, match.start() - context_chars)
    end = min(len(content), match.end() + context_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    before = content[start : match.start()]
    after = content[match.end() : end]
    return f"{prefix}{before}**{match.group()}**{after}{suffix}"


def search_messages(
    conn: duckdb.DuckDBPyConnection,
    *,
    q: str,
    session_id: str | None = None,
    agent_id: str | None = None,
    role: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Full-text search across message content. Returns results with snippets."""
    clauses = ["regexp_matches(content, ?)"]
    params: list = [q]

    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if agent_id:
        clauses.append("agent_id = ?")
        params.append(agent_id)
    if role:
        clauses.append("role = ?")
        params.append(role)

    where = " AND ".join(clauses)
    params.extend([limit, offset])

    rows = conn.execute(
        f"""
        SELECT message_id, session_id, agent_id, role, sequence, timestamp,
               content, content_bytes
        FROM messages
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()

    columns = [desc[0] for desc in conn.description]
    results = []
    for row in rows:
        rec = dict(zip(columns, row))
        content = rec.pop("content", None) or ""
        rec["content_preview"] = content[:500]
        rec["snippet"] = _build_snippet(content, q)
        results.append(rec)

    return results


def get_agent_messages(
    conn: duckdb.DuckDBPyConnection,
    agent_id: str,
) -> list[dict]:
    """Get all messages for a specific agent, ordered by sequence."""
    rows = conn.execute(
        """
        SELECT message_id, session_id, agent_id, role, sequence, timestamp,
               content, content_bytes
        FROM messages
        WHERE agent_id = ?
        ORDER BY sequence ASC
        """,
        [agent_id],
    ).fetchall()

    columns = [desc[0] for desc in conn.description]
    results = []
    for row in rows:
        rec = dict(zip(columns, row))
        content = rec.pop("content", None) or ""
        rec["content_preview"] = content[:500]
        rec["content"] = content
        results.append(rec)

    return results


def get_session_messages(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Get all messages across all agents in a session, ordered by timestamp."""
    rows = conn.execute(
        """
        SELECT message_id, session_id, agent_id, role, sequence, timestamp,
               content, content_bytes
        FROM messages
        WHERE session_id = ?
        ORDER BY timestamp ASC
        LIMIT ? OFFSET ?
        """,
        [session_id, limit, offset],
    ).fetchall()

    columns = [desc[0] for desc in conn.description]
    results = []
    for row in rows:
        rec = dict(zip(columns, row))
        content = rec.pop("content", None) or ""
        rec["content_preview"] = content[:500]
        results.append(rec)

    return results
