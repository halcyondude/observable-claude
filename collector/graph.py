import json
import logging
from datetime import datetime, timezone

from real_ladybug import Database, Connection

logger = logging.getLogger(__name__)

DDL_STATEMENTS = [
    "CREATE NODE TABLE IF NOT EXISTS Session (session_id STRING, cwd STRING, start_ts STRING, end_ts STRING, PRIMARY KEY (session_id))",
    "CREATE NODE TABLE IF NOT EXISTS Agent (agent_id STRING, agent_type STRING, session_id STRING, start_ts STRING, end_ts STRING, status STRING, PRIMARY KEY (agent_id))",
    "CREATE NODE TABLE IF NOT EXISTS Skill (name STRING, path STRING, PRIMARY KEY (name))",
    "CREATE NODE TABLE IF NOT EXISTS Tool (name STRING, PRIMARY KEY (name))",
    "CREATE REL TABLE IF NOT EXISTS SPAWNED (FROM Session TO Agent, FROM Agent TO Agent, prompt STRING, depth INT64, spawned_at STRING)",
    "CREATE REL TABLE IF NOT EXISTS LOADED (FROM Agent TO Skill, loaded_at STRING)",
    "CREATE REL TABLE IF NOT EXISTS INVOKED (FROM Agent TO Tool, tool_use_id STRING, tool_input STRING, start_ts STRING, end_ts STRING, duration_ms INT64, status STRING, tool_response STRING)",
]

DROP_STATEMENTS = [
    "DROP TABLE IF EXISTS INVOKED",
    "DROP TABLE IF EXISTS LOADED",
    "DROP TABLE IF EXISTS SPAWNED",
    "DROP TABLE IF EXISTS Tool",
    "DROP TABLE IF EXISTS Skill",
    "DROP TABLE IF EXISTS Agent",
    "DROP TABLE IF EXISTS Session",
]


def init_graph(db_path: str) -> tuple[Database, Connection]:
    """Open or create a LadybugDB database and run DDL. Returns (db, conn)."""
    db = Database(db_path)
    conn = Connection(db)
    for stmt in DDL_STATEMENTS:
        conn.execute(stmt)
    return db, conn


def reset_graph(conn: Connection) -> None:
    """Drop and recreate all graph tables (clean slate for replay)."""
    for stmt in DROP_STATEMENTS:
        conn.execute(stmt)
    for stmt in DDL_STATEMENTS:
        conn.execute(stmt)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract(event: dict, nested_key: str, flat_key: str) -> str | None:
    """Extract a value from nested event/session structure or flat top-level."""
    parts = nested_key.split(".", 1)
    if len(parts) == 2:
        val = event.get(parts[0], {}).get(parts[1])
        if val is not None:
            return val
    return event.get(flat_key)


def materialize_event(conn: Connection, event: dict) -> None:
    """Route an event to the appropriate Cypher mutation. Safe to call repeatedly."""
    event_type = _extract(event, "event.event_type", "event_type")
    if not event_type:
        return

    handler = _HANDLERS.get(event_type)
    if handler is None:
        return

    try:
        handler(conn, event)
    except Exception:
        logger.exception("Graph materialization failed for event_type=%s", event_type)


# --- Per-event handlers ---


def _handle_session_start(conn: Connection, event: dict) -> None:
    session_id = _extract(event, "session.session_id", "session_id")
    cwd = _extract(event, "session.cwd", "cwd") or ""
    ts = _extract(event, "event.timestamp", "timestamp") or _now_iso()

    conn.execute(
        "MERGE (s:Session {session_id: $sid}) SET s.cwd = $cwd, s.start_ts = $ts",
        parameters={"sid": session_id, "cwd": cwd, "ts": ts},
    )


def _handle_session_end(conn: Connection, event: dict) -> None:
    session_id = _extract(event, "session.session_id", "session_id")
    ts = _extract(event, "event.timestamp", "timestamp") or _now_iso()

    conn.execute(
        "MATCH (s:Session {session_id: $sid}) SET s.end_ts = $ts",
        parameters={"sid": session_id, "ts": ts},
    )


def _handle_subagent_start(conn: Connection, event: dict) -> None:
    agent_id = _extract(event, "session.agent_id", "agent_id")
    agent_type = _extract(event, "session.agent_type", "agent_type") or "unknown"
    session_id = _extract(event, "session.session_id", "session_id")
    ts = _extract(event, "event.timestamp", "timestamp") or _now_iso()
    parent_agent_id = _extract(event, "event.parent_agent_id", "parent_agent_id")
    prompt = _extract(event, "event.prompt", "prompt") or ""
    depth = _extract(event, "event.depth", "depth") or 0

    # Create the agent node
    conn.execute(
        "MERGE (a:Agent {agent_id: $aid}) "
        "SET a.agent_type = $atype, a.session_id = $sid, a.start_ts = $ts, a.status = 'running'",
        parameters={"aid": agent_id, "atype": agent_type, "sid": session_id, "ts": ts},
    )

    # Create SPAWNED edge from parent
    if parent_agent_id:
        # Parent is another agent
        conn.execute(
            "MERGE (p:Agent {agent_id: $pid})",
            parameters={"pid": parent_agent_id},
        )
        conn.execute(
            "MATCH (p:Agent {agent_id: $pid}), (a:Agent {agent_id: $aid}) "
            "CREATE (p)-[:SPAWNED {prompt: $prompt, depth: $depth, spawned_at: $ts}]->(a)",
            parameters={
                "pid": parent_agent_id,
                "aid": agent_id,
                "prompt": prompt,
                "depth": depth,
                "ts": ts,
            },
        )
    elif session_id:
        # Parent is the session
        conn.execute(
            "MERGE (s:Session {session_id: $sid})",
            parameters={"sid": session_id},
        )
        conn.execute(
            "MATCH (s:Session {session_id: $sid}), (a:Agent {agent_id: $aid}) "
            "CREATE (s)-[:SPAWNED {prompt: $prompt, depth: $depth, spawned_at: $ts}]->(a)",
            parameters={
                "sid": session_id,
                "aid": agent_id,
                "prompt": prompt,
                "depth": int(depth),
                "ts": ts,
            },
        )


def _handle_subagent_stop(conn: Connection, event: dict) -> None:
    agent_id = _extract(event, "session.agent_id", "agent_id")
    ts = _extract(event, "event.timestamp", "timestamp") or _now_iso()
    status = _extract(event, "event.status", "status") or "complete"

    conn.execute(
        "MATCH (a:Agent {agent_id: $aid}) SET a.end_ts = $ts, a.status = $status",
        parameters={"aid": agent_id, "ts": ts, "status": status},
    )


def _handle_stop(conn: Connection, event: dict) -> None:
    agent_id = _extract(event, "session.agent_id", "agent_id")
    if not agent_id:
        return
    conn.execute(
        "MATCH (a:Agent {agent_id: $aid}) SET a.status = 'complete'",
        parameters={"aid": agent_id},
    )


def _handle_pre_tool_use(conn: Connection, event: dict) -> None:
    agent_id = _extract(event, "session.agent_id", "agent_id")
    tool_name = _extract(event, "event.tool_name", "tool_name") or "unknown"
    tool_use_id = _extract(event, "event.tool_use_id", "tool_use_id")
    ts = _extract(event, "event.timestamp", "timestamp") or _now_iso()

    # Extract tool_input — may be nested under event.tool_input
    tool_input_raw = _extract(event, "event.tool_input", "tool_input")
    if isinstance(tool_input_raw, dict):
        tool_input = json.dumps(tool_input_raw)
    elif tool_input_raw is not None:
        tool_input = str(tool_input_raw)
    else:
        tool_input = ""

    # Ensure Tool node exists
    conn.execute(
        "MERGE (t:Tool {name: $name})",
        parameters={"name": tool_name},
    )

    # Ensure Agent node exists (may not have seen SubagentStart for the root agent)
    session_id = _extract(event, "session.session_id", "session_id")
    agent_type = _extract(event, "session.agent_type", "agent_type") or "unknown"
    conn.execute(
        "MERGE (a:Agent {agent_id: $aid}) "
        "ON CREATE SET a.agent_type = $atype, a.session_id = $sid, a.status = 'running'",
        parameters={"aid": agent_id, "atype": agent_type, "sid": session_id},
    )

    # Create INVOKED edge
    conn.execute(
        "MATCH (a:Agent {agent_id: $aid}), (t:Tool {name: $tname}) "
        "CREATE (a)-[:INVOKED {tool_use_id: $tuid, tool_input: $input, start_ts: $ts, status: 'pending'}]->(t)",
        parameters={
            "aid": agent_id,
            "tname": tool_name,
            "tuid": tool_use_id,
            "input": tool_input,
            "ts": ts,
        },
    )


def _handle_post_tool_use(conn: Connection, event: dict, failed: bool = False) -> None:
    tool_use_id = _extract(event, "event.tool_use_id", "tool_use_id")
    ts = _extract(event, "event.timestamp", "timestamp") or _now_iso()
    status = "failed" if failed else "success"

    # Extract duration
    duration_ms = _extract(event, "event.duration_ms", "duration_ms")
    if duration_ms is not None:
        duration_ms = int(duration_ms)
    else:
        duration_ms = 0

    # Extract tool_response — truncate to avoid huge graph properties
    tool_response_raw = _extract(event, "event.tool_response", "tool_response")
    if isinstance(tool_response_raw, dict):
        tool_response = json.dumps(tool_response_raw)[:2000]
    elif tool_response_raw is not None:
        tool_response = str(tool_response_raw)[:2000]
    else:
        tool_response = ""

    conn.execute(
        "MATCH (a:Agent)-[r:INVOKED {tool_use_id: $tuid}]->(t:Tool) "
        "SET r.end_ts = $ts, r.duration_ms = $dur, r.status = $status, r.tool_response = $resp",
        parameters={
            "tuid": tool_use_id,
            "ts": ts,
            "dur": duration_ms,
            "status": status,
            "resp": tool_response,
        },
    )


def _handle_post_tool_use_failure(conn: Connection, event: dict) -> None:
    _handle_post_tool_use(conn, event, failed=True)


_HANDLERS = {
    "SessionStart": _handle_session_start,
    "SessionEnd": _handle_session_end,
    "SubagentStart": _handle_subagent_start,
    "SubagentStop": _handle_subagent_stop,
    "Stop": _handle_stop,
    "PreToolUse": _handle_pre_tool_use,
    "PostToolUse": _handle_post_tool_use,
    "PostToolUseFailure": _handle_post_tool_use_failure,
    # No-ops: DuckDB only
    "UserPromptSubmit": lambda conn, event: None,
    "Notification": lambda conn, event: None,
    "PermissionRequest": lambda conn, event: None,
    "PreCompact": lambda conn, event: None,
}


# --- Query functions ---


def get_session_graph(conn: Connection, session_id: str) -> dict:
    """Return Cytoscape.js compatible JSON for a session's graph."""
    nodes = []
    edges = []

    # Session node
    result = conn.execute(
        "MATCH (s:Session {session_id: $sid}) RETURN s.session_id, s.cwd, s.start_ts, s.end_ts",
        parameters={"sid": session_id},
    )
    for row in result.get_all():
        nodes.append({
            "data": {
                "id": row[0],
                "label": f"Session",
                "type": "Session",
                "session_id": row[0],
                "cwd": row[1],
                "start_ts": row[2],
                "end_ts": row[3],
            }
        })

    # Agent nodes for this session
    result = conn.execute(
        "MATCH (a:Agent {session_id: $sid}) RETURN a.agent_id, a.agent_type, a.start_ts, a.end_ts, a.status",
        parameters={"sid": session_id},
    )
    for row in result.get_all():
        nodes.append({
            "data": {
                "id": row[0],
                "label": row[1] or "Agent",
                "type": "Agent",
                "agent_id": row[0],
                "agent_type": row[1],
                "start_ts": row[2],
                "end_ts": row[3],
                "status": row[4],
            }
        })

    # Tool nodes invoked by agents in this session
    result = conn.execute(
        "MATCH (a:Agent {session_id: $sid})-[r:INVOKED]->(t:Tool) "
        "RETURN DISTINCT t.name",
        parameters={"sid": session_id},
    )
    for row in result.get_all():
        nodes.append({
            "data": {
                "id": f"tool:{row[0]}",
                "label": row[0],
                "type": "Tool",
                "name": row[0],
            }
        })

    # SPAWNED edges: Session -> Agent
    result = conn.execute(
        "MATCH (s:Session {session_id: $sid})-[r:SPAWNED]->(a:Agent) "
        "RETURN s.session_id, a.agent_id, r.prompt, r.depth, r.spawned_at",
        parameters={"sid": session_id},
    )
    for row in result.get_all():
        edges.append({
            "data": {
                "source": row[0],
                "target": row[1],
                "label": "SPAWNED",
                "prompt": row[2],
                "depth": row[3],
                "spawned_at": row[4],
            }
        })

    # SPAWNED edges: Agent -> Agent (within this session)
    result = conn.execute(
        "MATCH (p:Agent {session_id: $sid})-[r:SPAWNED]->(c:Agent) "
        "RETURN p.agent_id, c.agent_id, r.prompt, r.depth, r.spawned_at",
        parameters={"sid": session_id},
    )
    for row in result.get_all():
        edges.append({
            "data": {
                "source": row[0],
                "target": row[1],
                "label": "SPAWNED",
                "prompt": row[2],
                "depth": row[3],
                "spawned_at": row[4],
            }
        })

    # INVOKED edges
    result = conn.execute(
        "MATCH (a:Agent {session_id: $sid})-[r:INVOKED]->(t:Tool) "
        "RETURN a.agent_id, t.name, r.tool_use_id, r.start_ts, r.end_ts, r.duration_ms, r.status",
        parameters={"sid": session_id},
    )
    for row in result.get_all():
        edges.append({
            "data": {
                "source": row[0],
                "target": f"tool:{row[1]}",
                "label": "INVOKED",
                "tool_use_id": row[2],
                "start_ts": row[3],
                "end_ts": row[4],
                "duration_ms": row[5],
                "status": row[6],
            }
        })

    return {"nodes": nodes, "edges": edges}


def get_session_timeline(conn: Connection, session_id: str) -> list[dict]:
    """Return Gantt-compatible timeline data for a session."""
    timeline = []

    # Get all agents for the session with their spawn depth
    result = conn.execute(
        "MATCH (a:Agent {session_id: $sid}) "
        "OPTIONAL MATCH ()-[r:SPAWNED]->(a) "
        "RETURN a.agent_id, a.agent_type, a.start_ts, a.end_ts, a.status, r.depth",
        parameters={"sid": session_id},
    )

    agents = {}
    for row in result.get_all():
        agent_id = row[0]
        agents[agent_id] = {
            "agent_id": agent_id,
            "agent_type": row[1],
            "start_ts": row[2],
            "end_ts": row[3],
            "status": row[4],
            "depth": row[5] if row[5] is not None else 0,
            "tool_events": [],
        }

    # Get tool events for each agent
    result = conn.execute(
        "MATCH (a:Agent {session_id: $sid})-[r:INVOKED]->(t:Tool) "
        "RETURN a.agent_id, r.tool_use_id, t.name, r.start_ts, r.end_ts, r.status "
        "ORDER BY r.start_ts",
        parameters={"sid": session_id},
    )

    for row in result.get_all():
        agent_id = row[0]
        if agent_id in agents:
            agents[agent_id]["tool_events"].append({
                "tool_use_id": row[1],
                "tool_name": row[2],
                "start_ts": row[3],
                "end_ts": row[4],
                "status": row[5],
            })

    # Sort by start_ts
    timeline = sorted(agents.values(), key=lambda a: a.get("start_ts") or "")
    return timeline
