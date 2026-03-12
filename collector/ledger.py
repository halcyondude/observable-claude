import gzip
import re
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
CREATE INDEX IF NOT EXISTS idx_cwd ON events(cwd);

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
CREATE INDEX IF NOT EXISTS idx_msg_hash ON messages(content_hash);

CREATE TABLE IF NOT EXISTS saved_sessions (
  session_id    VARCHAR PRIMARY KEY,
  name          VARCHAR NOT NULL,
  notes         TEXT,
  tags          JSON,
  saved_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  event_count   INTEGER,
  agent_count   INTEGER,
  duration_seconds DOUBLE,
  export_count  INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_saved_at ON saved_sessions(saved_at);
"""

CCOBS_VERSION = 1


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


# --- Sessions ---


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


def get_session_events(conn: duckdb.DuckDBPyConnection, session_id: str) -> list[dict]:
    """Return all events for a session ordered chronologically (ASC)."""
    rows = conn.execute(
        "SELECT * FROM events WHERE session_id = ? ORDER BY received_at ASC",
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

    # Get saved session IDs
    saved_rows = conn.execute(
        "SELECT session_id FROM saved_sessions"
    ).fetchall()
    saved_sessions = {row[0] for row in saved_rows}

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
            "saved": session_id in saved_sessions,
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


def get_activity_histogram(
    conn: duckdb.DuckDBPyConnection,
    bucket_seconds: int = 60,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    """Return event counts bucketed by time interval and cwd."""
    clauses = []
    params: list = []

    if since is not None:
        clauses.append("received_at >= ?::TIMESTAMPTZ")
        params.append(since)
    if until is not None:
        clauses.append("received_at < ?::TIMESTAMPTZ")
        params.append(until)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    rows = conn.execute(
        f"""
        SELECT
            to_timestamp(
                FLOOR(epoch(received_at) / ?) * ?
            ) AS timestamp,
            COUNT(*) AS count,
            cwd
        FROM events
        {where}
        GROUP BY timestamp, cwd
        ORDER BY timestamp ASC, cwd
        """,
        [bucket_seconds, bucket_seconds, *params],
    ).fetchall()

    columns = [desc[0] for desc in conn.description]
    return [dict(zip(columns, row)) for row in rows]


def get_session_summary(conn: duckdb.DuckDBPyConnection) -> dict:
    """Return aggregate session counts: total, active, and distinct workspaces."""
    row = conn.execute(
        """
        SELECT
            COUNT(DISTINCT session_id) AS total,
            COUNT(DISTINCT CASE
                WHEN session_id IN (
                    SELECT session_id FROM events WHERE event_type = 'SessionStart'
                ) AND session_id NOT IN (
                    SELECT session_id FROM events WHERE event_type = 'SessionEnd'
                ) THEN session_id
            END) AS active,
            COUNT(DISTINCT cwd) AS workspaces
        FROM events
        WHERE session_id IS NOT NULL
        """
    ).fetchone()
    return {"total": row[0], "active": row[1], "workspaces": row[2]}


# --- Saved Sessions ---


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


def _build_snippet(content: str, query: str, context_chars: int = 50) -> str | None:
    """Build a snippet showing the match in context with **bold** markers."""
    if not content or not query:
        return None
    try:
        match = re.search(query, content, re.IGNORECASE)
    except re.error:
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
    clauses = ["content IS NOT NULL", "contains(lower(content), lower(?))"]
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
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Get all messages across all agents in a session, ordered by timestamp."""
    rows = conn.execute(
        """
        SELECT message_id, session_id, agent_id, role, sequence, timestamp,
               content, content_bytes, synthetic
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


def get_session_message_count(conn: duckdb.DuckDBPyConnection, session_id: str) -> int:
    """Return total message count for a session."""
    result = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE session_id = ?",
        [session_id],
    ).fetchone()
    return result[0] if result else 0


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


# --- Export / Import (.ccobs) ---


def _serialize_row(row: dict) -> dict:
    """Convert DuckDB row values to JSON-safe types."""
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _get_session_events_for_export(conn: duckdb.DuckDBPyConnection, session_id: str) -> list[dict]:
    """Return all events for a session, oldest first, serialized for JSON."""
    rows = conn.execute(
        "SELECT * FROM events WHERE session_id = ? ORDER BY received_at ASC",
        [session_id],
    ).fetchall()
    columns = [desc[0] for desc in conn.description]
    return [_serialize_row(dict(zip(columns, row))) for row in rows]


def _get_saved_session_meta(conn: duckdb.DuckDBPyConnection, session_id: str) -> dict | None:
    """Return saved_sessions metadata if this session is bookmarked."""
    rows = conn.execute(
        "SELECT * FROM saved_sessions WHERE session_id = ?",
        [session_id],
    ).fetchall()
    if not rows:
        return None
    columns = [desc[0] for desc in conn.description]
    return _serialize_row(dict(zip(columns, rows[0])))


def _compute_stats(events: list[dict]) -> dict:
    """Compute summary stats from an event list."""
    agent_ids = set()
    tool_calls = 0
    start_ts = None
    end_ts = None

    for ev in events:
        if ev.get("agent_id"):
            agent_ids.add(ev["agent_id"])
        if ev.get("event_type") == "PreToolUse":
            tool_calls += 1
        ts = ev.get("received_at")
        if ts:
            if start_ts is None or ts < start_ts:
                start_ts = ts
            if end_ts is None or ts > end_ts:
                end_ts = ts

    duration = 0.0
    if start_ts and end_ts:
        try:
            t0 = datetime.fromisoformat(start_ts) if isinstance(start_ts, str) else start_ts
            t1 = datetime.fromisoformat(end_ts) if isinstance(end_ts, str) else end_ts
            duration = (t1 - t0).total_seconds()
        except (ValueError, TypeError):
            pass

    return {
        "event_count": len(events),
        "agent_count": len(agent_ids),
        "duration_seconds": round(duration, 1),
        "tool_calls": tool_calls,
    }


def _get_session_messages_for_export(conn: duckdb.DuckDBPyConnection, session_id: str) -> list[dict]:
    """Return all messages for a session, serialized for export."""
    rows = conn.execute(
        """
        SELECT message_id, event_id, session_id, agent_id, role, sequence,
               timestamp, content, content_bytes, synthetic, metadata
        FROM messages
        WHERE session_id = ?
        ORDER BY timestamp ASC
        """,
        [session_id],
    ).fetchall()
    columns = [desc[0] for desc in conn.description]
    return [_serialize_row(dict(zip(columns, row))) for row in rows]


def export_session(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    graph_data: dict,
    timeline_data,
) -> dict:
    """Build the .ccobs export dict for a session.

    graph_data and timeline_data should be pre-fetched from the graph module.
    """
    events = _get_session_events_for_export(conn, session_id)
    if not events:
        raise ValueError(f"No events found for session {session_id}")

    saved_meta = _get_saved_session_meta(conn, session_id)
    stats = _compute_stats(events)
    messages = _get_session_messages_for_export(conn, session_id)

    # Derive session envelope
    first = events[0]
    last = events[-1]
    cwd = first.get("cwd", "")
    workspace_name = cwd.rstrip("/").rsplit("/", 1)[-1] if "/" in cwd else cwd

    session_block = {
        "session_id": session_id,
        "cwd": cwd,
        "start_ts": first.get("received_at", ""),
        "end_ts": last.get("received_at", ""),
        "workspace": {"path": cwd, "name": workspace_name},
    }
    if saved_meta:
        session_block["name"] = saved_meta.get("name", "")
        session_block["notes"] = saved_meta.get("notes", "")
        tags = saved_meta.get("tags")
        session_block["tags"] = json.loads(tags) if isinstance(tags, str) else (tags or [])

    # Increment export_count if bookmarked
    if saved_meta:
        conn.execute(
            "UPDATE saved_sessions SET export_count = export_count + 1 WHERE session_id = ?",
            [session_id],
        )

    return {
        "version": CCOBS_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "session": session_block,
        "events": events,
        "messages": messages,
        "graph": graph_data,
        "timeline": timeline_data,
        "stats": stats,
    }


def export_session_gzip(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    graph_data: dict,
    timeline_data,
) -> bytes:
    """Return gzipped JSON bytes for a .ccobs file."""
    data = export_session(conn, session_id, graph_data, timeline_data)
    return gzip.compress(json.dumps(data, default=str).encode("utf-8"))


def import_session(conn: duckdb.DuckDBPyConnection, data: dict) -> dict:
    """Import a .ccobs dict into DuckDB.

    Returns {imported: N, skipped: N, session_id: "..."}.
    """
    version = data.get("version")
    if version != CCOBS_VERSION:
        raise ValueError(f"Unsupported .ccobs version: {version} (expected {CCOBS_VERSION})")

    session_info = data.get("session", {})
    session_id = session_info.get("session_id")
    if not session_id:
        raise ValueError("Missing session_id in .ccobs file")

    events = data.get("events", [])
    imported = 0
    skipped = 0

    for ev in events:
        eid = ev.get("event_id")
        if not eid:
            skipped += 1
            continue

        existing = conn.execute(
            "SELECT 1 FROM events WHERE event_id = ?", [eid]
        ).fetchone()
        if existing:
            skipped += 1
            continue

        received_at = ev.get("received_at")
        conn.execute(
            """
            INSERT INTO events (event_id, received_at, event_type, session_id, agent_id, agent_type, tool_use_id, tool_name, cwd, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                eid, received_at, ev.get("event_type", "unknown"),
                ev.get("session_id"), ev.get("agent_id"), ev.get("agent_type"),
                ev.get("tool_use_id"), ev.get("tool_name"), ev.get("cwd"),
                ev.get("payload"),
            ],
        )
        imported += 1

    # Import messages if present
    messages_imported = 0
    for msg in data.get("messages", []):
        mid = msg.get("message_id")
        if not mid:
            continue
        existing = conn.execute(
            "SELECT 1 FROM messages WHERE message_id = ?", [mid]
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """
            INSERT INTO messages (message_id, event_id, session_id, agent_id, role, sequence,
                                  timestamp, content, content_hash, content_bytes, synthetic, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                mid, msg.get("event_id"), msg.get("session_id"), msg.get("agent_id"),
                msg.get("role", "user"), msg.get("sequence", 0), msg.get("timestamp"),
                msg.get("content"), msg.get("content_hash"), msg.get("content_bytes", 0),
                msg.get("synthetic", False), msg.get("metadata"),
            ],
        )
        messages_imported += 1

    # Upsert into saved_sessions
    name = session_info.get("name") or f"Imported: {session_id[:12]}"
    notes = session_info.get("notes", "")
    tags = json.dumps(session_info.get("tags", []))

    existing_saved = conn.execute(
        "SELECT 1 FROM saved_sessions WHERE session_id = ?", [session_id]
    ).fetchone()
    if existing_saved:
        conn.execute(
            "UPDATE saved_sessions SET name = ?, notes = ?, tags = ? WHERE session_id = ?",
            [name, notes, tags, session_id],
        )
    else:
        conn.execute(
            "INSERT INTO saved_sessions (session_id, name, notes, tags) VALUES (?, ?, ?, ?)",
            [session_id, name, notes, tags],
        )

    return {"imported": imported, "skipped": skipped, "messages_imported": messages_imported, "session_id": session_id}


def parse_ccobs(raw_bytes: bytes) -> dict:
    """Parse raw bytes (gzipped or plain JSON) into a .ccobs dict."""
    try:
        decompressed = gzip.decompress(raw_bytes)
    except (gzip.BadGzipFile, OSError):
        decompressed = raw_bytes
    return json.loads(decompressed)
