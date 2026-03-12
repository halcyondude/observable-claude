import gzip
import uuid
import json
import duckdb
from datetime import datetime, timezone


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
CREATE TABLE IF NOT EXISTS saved_sessions (
  session_id    VARCHAR PRIMARY KEY,
  name          VARCHAR NOT NULL,
  notes         TEXT,
  saved_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  tags          JSON,
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


def _get_session_events(conn: duckdb.DuckDBPyConnection, session_id: str) -> list[dict]:
    """Return all events for a session, oldest first."""
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


def export_session(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    graph_data: dict,
    timeline_data,
) -> dict:
    """Build the .ccobs export dict for a session.

    graph_data and timeline_data should be pre-fetched from the graph module
    (get_session_graph / get_session_timeline) so the ledger module doesn't
    depend on the graph layer.
    """
    events = _get_session_events(conn, session_id)
    if not events:
        raise ValueError(f"No events found for session {session_id}")

    saved_meta = _get_saved_session_meta(conn, session_id)
    stats = _compute_stats(events)

    # Derive session envelope
    first = events[0]
    last = events[-1]
    session_block = {
        "session_id": session_id,
        "cwd": first.get("cwd", ""),
        "start_ts": first.get("received_at", ""),
        "end_ts": last.get("received_at", ""),
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

        # Check if event already exists (dedup by event_id)
        existing = conn.execute(
            "SELECT 1 FROM events WHERE event_id = ?", [eid]
        ).fetchone()
        if existing:
            skipped += 1
            continue

        # Parse received_at back to a timestamp-compatible string
        received_at = ev.get("received_at")

        conn.execute(
            """
            INSERT INTO events (event_id, received_at, event_type, session_id, agent_id, agent_type, tool_use_id, tool_name, cwd, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                eid,
                received_at,
                ev.get("event_type", "unknown"),
                ev.get("session_id"),
                ev.get("agent_id"),
                ev.get("agent_type"),
                ev.get("tool_use_id"),
                ev.get("tool_name"),
                ev.get("cwd"),
                ev.get("payload"),
            ],
        )
        imported += 1

    # Upsert into saved_sessions so imported sessions appear as bookmarked
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

    return {"imported": imported, "skipped": skipped, "session_id": session_id}


def parse_ccobs(raw_bytes: bytes) -> dict:
    """Parse raw bytes (gzipped or plain JSON) into a .ccobs dict."""
    try:
        decompressed = gzip.decompress(raw_bytes)
    except (gzip.BadGzipFile, OSError):
        # Try as plain JSON
        decompressed = raw_bytes

    return json.loads(decompressed)
