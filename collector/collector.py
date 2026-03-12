import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query, UploadFile, File
from fastapi.responses import JSONResponse, Response
from sse_starlette.sse import EventSourceResponse

from anthropic import Anthropic

from .ledger import (
    init_db, write_event, query_events,
    get_sessions, get_active_sessions, get_grouped_sessions,
    get_session_events, get_session_event_count,
    get_activity_histogram, get_session_summary,
    write_message, get_next_sequence, get_agent_messages, get_session_messages,
    get_session_message_count, get_agent_tool_summary, search_messages,
    save_session, unsave_session, get_saved_sessions, update_saved_session,
    export_session_gzip, import_session, parse_ccobs,
)
from .graph import (
    init_graph, materialize_event, materialize_message,
    get_session_graph, get_session_timeline, reset_graph,
)
from . import nl_query

logger = logging.getLogger(__name__)

_start_time: float = 0.0
_db = None
_graph_conn = None
_graph_db = None
_anthropic_client = None
_sse_clients: list[asyncio.Queue] = []

# Replay state: keyed by session_id
_replay_states: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _db, _graph_db, _graph_conn, _anthropic_client, _start_time
    db_path = os.environ.get("DUCKDB_PATH", "./data/duckdb/events.db")
    ladybug_path = os.environ.get("LADYBUG_PATH", "./data/ladybug")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(os.path.dirname(ladybug_path) or ".", exist_ok=True)
    _db = init_db(db_path)
    _graph_db, _graph_conn = init_graph(ladybug_path)
    _start_time = time.time()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        _anthropic_client = Anthropic()
    else:
        logger.warning("ANTHROPIC_API_KEY not set — /api/ask endpoint will be unavailable")

    yield
    if _db:
        _db.close()


app = FastAPI(lifespan=lifespan)


# --- Helpers ---


def _truncate(text: str, max_len: int = 500) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _extract_field(payload: dict, nested_key: str, flat_key: str):
    """Extract a value from nested event/session structure or flat top-level."""
    parts = nested_key.split(".", 1)
    if len(parts) == 2:
        val = payload.get(parts[0], {}).get(parts[1])
        if val is not None:
            return val
    return payload.get(flat_key)


def _broadcast_sse(event_type: str, data: str) -> None:
    dead = []
    for q in _sse_clients:
        try:
            q.put_nowait((event_type, data))
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _sse_clients.remove(q)


# --- Message extraction ---


def _write_and_materialize_message(
    event_id: str,
    session_id: str,
    agent_id: str,
    role: str,
    content: str,
    synthetic: bool = False,
    metadata: dict | None = None,
) -> str | None:
    """Write a message to DuckDB and materialize in graph. Returns message_id."""
    if not _db or not session_id or not agent_id:
        return None

    sequence = get_next_sequence(_db, agent_id)
    message_id = write_message(
        _db,
        session_id=session_id,
        agent_id=agent_id,
        role=role,
        content=content,
        event_id=event_id,
        sequence=sequence,
        synthetic=synthetic,
        metadata=metadata,
    )

    if _graph_conn:
        try:
            materialize_message(
                _graph_conn,
                message_id=message_id,
                agent_id=agent_id,
                session_id=session_id,
                role=role,
                sequence=sequence,
                content_preview=_truncate(content),
                synthetic=synthetic,
            )
        except Exception:
            logger.exception("Message graph materialization failed for %s", message_id)

    # Broadcast message SSE event
    msg_data = json.dumps({
        "message_id": message_id,
        "agent_id": agent_id,
        "session_id": session_id,
        "role": role,
        "sequence": sequence,
        "synthetic": synthetic,
        "content_preview": _truncate(content),
    })
    _broadcast_sse("message", msg_data)

    return message_id


def _handle_subagent_stop_message(event_id: str, payload: dict) -> None:
    """Infer agent response from SubagentStop event."""
    agent_id = _extract_field(payload, "session.agent_id", "agent_id")
    session_id = _extract_field(payload, "session.session_id", "session_id")
    if not agent_id or not session_id:
        return

    result_text = _extract_field(payload, "event.result", "result")
    output_text = _extract_field(payload, "event.output", "output")
    response_text = result_text or output_text

    if response_text:
        if isinstance(response_text, dict):
            response_text = json.dumps(response_text)
        _write_and_materialize_message(
            event_id=event_id,
            session_id=session_id,
            agent_id=agent_id,
            role="assistant",
            content=str(response_text),
            synthetic=False,
        )
    else:
        summary = get_agent_tool_summary(_db, agent_id)
        tool_list = ", ".join(summary["tools"][:5]) if summary["tools"] else "none"
        duration_ms = _extract_field(payload, "event.duration_ms", "duration_ms")
        dur_str = f" Duration: {duration_ms}ms." if duration_ms else ""

        content = (
            f"Agent completed. {summary['total']} tool calls ({tool_list}). "
            f"{summary['successes']} succeeded, {summary['failures']} failed.{dur_str}"
        )
        _write_and_materialize_message(
            event_id=event_id,
            session_id=session_id,
            agent_id=agent_id,
            role="assistant",
            content=content,
            synthetic=True,
        )


def _handle_pre_tool_message(event_id: str, payload: dict) -> None:
    """Write a tool message for PreToolUse events."""
    agent_id = _extract_field(payload, "session.agent_id", "agent_id")
    session_id = _extract_field(payload, "session.session_id", "session_id")
    tool_name = _extract_field(payload, "event.tool_name", "tool_name") or "unknown"
    if not agent_id or not session_id:
        return

    tool_input_raw = _extract_field(payload, "event.tool_input", "tool_input")
    if isinstance(tool_input_raw, dict):
        input_str = json.dumps(tool_input_raw)
    elif tool_input_raw is not None:
        input_str = str(tool_input_raw)
    else:
        input_str = ""

    content = f"Tool call: {tool_name}\nInput: {_truncate(input_str)}"
    tool_use_id = _extract_field(payload, "event.tool_use_id", "tool_use_id")

    _write_and_materialize_message(
        event_id=event_id,
        session_id=session_id,
        agent_id=agent_id,
        role="tool",
        content=content,
        synthetic=False,
        metadata={"tool_name": tool_name, "tool_use_id": tool_use_id, "phase": "pre"},
    )


def _handle_post_tool_message(event_id: str, payload: dict) -> None:
    """Write a tool message for PostToolUse events."""
    agent_id = _extract_field(payload, "session.agent_id", "agent_id")
    session_id = _extract_field(payload, "session.session_id", "session_id")
    tool_name = _extract_field(payload, "event.tool_name", "tool_name") or "unknown"
    if not agent_id or not session_id:
        return

    event_type = _extract_field(payload, "event.event_type", "event_type") or "PostToolUse"
    status = "failed" if "Failure" in event_type else "success"
    duration_ms = _extract_field(payload, "event.duration_ms", "duration_ms") or 0

    tool_response_raw = _extract_field(payload, "event.tool_response", "tool_response")
    if isinstance(tool_response_raw, dict):
        output_str = json.dumps(tool_response_raw)
    elif tool_response_raw is not None:
        output_str = str(tool_response_raw)
    else:
        output_str = ""

    content = (
        f"Tool result: {tool_name}\n"
        f"Status: {status}\n"
        f"Duration: {duration_ms}ms\n"
        f"Output: {_truncate(output_str)}"
    )
    tool_use_id = _extract_field(payload, "event.tool_use_id", "tool_use_id")

    _write_and_materialize_message(
        event_id=event_id,
        session_id=session_id,
        agent_id=agent_id,
        role="tool",
        content=content,
        synthetic=False,
        metadata={"tool_name": tool_name, "tool_use_id": tool_use_id, "phase": "post", "status": status},
    )


_MESSAGE_HANDLERS = {
    "SubagentStop": _handle_subagent_stop_message,
    "PreToolUse": _handle_pre_tool_message,
    "PostToolUse": _handle_post_tool_message,
    "PostToolUseFailure": _handle_post_tool_message,
}


# --- Core endpoints ---


@app.post("/events")
async def ingest_event(request: Request):
    payload = await request.json()
    event_id = write_event(_db, payload)

    if _graph_conn:
        try:
            materialize_event(_graph_conn, payload)
        except Exception:
            logger.exception("Graph materialization failed for event %s", event_id)

    event_type = payload.get("event", {}).get("event_type", payload.get("event_type", "unknown"))
    msg_handler = _MESSAGE_HANDLERS.get(event_type)
    if msg_handler:
        try:
            msg_handler(event_id, payload)
        except Exception:
            logger.exception("Message extraction failed for event %s", event_id)

    sse_data = json.dumps({"event_id": event_id, **payload})
    _broadcast_sse(event_type, sse_data)

    return {"event_id": event_id, "status": "ok"}


@app.get("/health")
async def health():
    total = _db.execute("SELECT COUNT(*) FROM events").fetchone()[0] if _db else 0
    return {
        "status": "ok",
        "events_total": total,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@app.get("/stream")
async def stream():
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    _sse_clients.append(queue)

    async def event_generator():
        try:
            while True:
                event_type, data = await queue.get()
                yield {"event": event_type, "data": data}
        except asyncio.CancelledError:
            pass
        finally:
            if queue in _sse_clients:
                _sse_clients.remove(queue)

    return EventSourceResponse(event_generator())


# --- Session endpoints ---


@app.get("/api/sessions")
async def list_sessions():
    return get_sessions(_db)


@app.get("/api/sessions/active")
async def list_active_sessions():
    return get_active_sessions(_db)


@app.get("/api/sessions/saved")
async def list_saved_sessions():
    return get_saved_sessions(_db)


@app.get("/api/sessions/grouped")
async def grouped_sessions(
    since: str | None = Query(None, description="ISO timestamp — only include sessions with events after this time"),
    limit: int | None = Query(None, ge=1, le=100, description="Max sessions per workspace"),
):
    groups = get_grouped_sessions(_db, since=since, limit=limit)

    # Enrich with branch info from LadybugDB if available
    if _graph_conn:
        try:
            result = _graph_conn.execute(
                "MATCH (s:Session) WHERE s.branch IS NOT NULL AND s.branch <> '' "
                "RETURN s.session_id, s.branch"
            )
            branch_map = {row[0]: row[1] for row in result.get_all()}
            for group in groups:
                for session in group["sessions"]:
                    branch = branch_map.get(session["session_id"], "")
                    if branch:
                        session["branch"] = branch
        except Exception:
            logger.exception("Failed to enrich sessions with branch data")

    return groups


@app.get("/api/sessions/activity")
async def session_activity(
    bucket: int = Query(60, ge=1, le=3600),
    since: str | None = Query(None),
    until: str | None = Query(None),
):
    """Time-bucketed event counts grouped by cwd for the Galaxy View time brush."""
    buckets = get_activity_histogram(_db, bucket_seconds=bucket, since=since, until=until)
    return {"bucket_seconds": bucket, "buckets": buckets}


@app.get("/api/sessions/summary")
async def session_summary():
    """Aggregate session counts for the dashboard header."""
    return get_session_summary(_db)


# --- Save/unsave endpoints ---


@app.post("/api/sessions/{session_id}/save")
async def save_session_endpoint(session_id: str, request: Request):
    body = await request.json()
    name = body.get("name", session_id)
    notes = body.get("notes")
    tags = body.get("tags")
    try:
        result = save_session(_db, session_id, name, notes, tags)
        return result
    except Exception as e:
        logger.exception("Failed to save session %s", session_id)
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.delete("/api/sessions/{session_id}/save")
async def unsave_session_endpoint(session_id: str):
    unsave_session(_db, session_id)
    return {"status": "ok", "session_id": session_id}


@app.put("/api/sessions/{session_id}/save")
async def update_saved_session_endpoint(session_id: str, request: Request):
    body = await request.json()
    name = body.get("name")
    notes = body.get("notes")
    tags = body.get("tags")
    result = update_saved_session(_db, session_id, name, notes, tags)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "Session not saved"})
    return result


# --- Export/Import endpoints ---


@app.get("/api/sessions/{session_id}/export")
async def export_session_endpoint(session_id: str):
    """Download a session as a .ccobs file (gzipped JSON)."""
    if not _db:
        return JSONResponse({"error": "Database not initialized"}, status_code=503)

    graph_data = {"nodes": [], "edges": []}
    timeline_data = []
    if _graph_conn:
        try:
            graph_data = get_session_graph(_graph_conn, session_id)
        except Exception:
            logger.exception("Failed to get graph for export of %s", session_id)
        try:
            timeline_data = get_session_timeline(_graph_conn, session_id)
        except Exception:
            logger.exception("Failed to get timeline for export of %s", session_id)

    try:
        gz_bytes = export_session_gzip(_db, session_id, graph_data, timeline_data)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)

    filename = f"{session_id[:12]}.ccobs"
    return Response(
        content=gz_bytes,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/sessions/import")
async def import_session_endpoint(file: UploadFile = File(...)):
    """Import a .ccobs file."""
    if not _db:
        return JSONResponse({"error": "Database not initialized"}, status_code=503)

    raw = await file.read()
    try:
        data = parse_ccobs(raw)
    except (json.JSONDecodeError, ValueError) as e:
        return JSONResponse({"error": f"Invalid .ccobs file: {e}"}, status_code=400)

    try:
        result = import_session(_db, data)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    return result


# --- Event endpoints ---


@app.get("/api/events")
async def list_events(
    event_type: str | None = Query(None),
    session_id: str | None = Query(None),
    agent_id: str | None = Query(None),
    tool_use_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    filters = {}
    if event_type:
        filters["event_type"] = event_type
    if session_id:
        filters["session_id"] = session_id
    if agent_id:
        filters["agent_id"] = agent_id
    if tool_use_id:
        filters["tool_use_id"] = tool_use_id
    return query_events(_db, filters=filters, limit=limit, offset=offset)


# --- Message endpoints ---


@app.get("/api/messages/search")
async def message_search(
    q: str = Query(..., min_length=1),
    session_id: str | None = Query(None),
    agent_id: str | None = Query(None),
    role: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Full-text search across message content."""
    try:
        return search_messages(
            _db, q=q, session_id=session_id, agent_id=agent_id,
            role=role, limit=limit, offset=offset,
        )
    except Exception as e:
        logger.exception("Message search failed for q=%s", q)
        return JSONResponse(
            status_code=400,
            content={"error": "Search failed", "details": str(e)},
        )


@app.get("/api/agents/{agent_id}/messages")
async def agent_messages(agent_id: str):
    return get_agent_messages(_db, agent_id)


@app.get("/api/sessions/{session_id}/messages")
async def session_messages(
    session_id: str,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get all messages across all agents in a session."""
    return get_session_messages(_db, session_id, limit=limit, offset=offset)


# --- Graph endpoints ---


@app.get("/api/sessions/{session_id}/graph")
async def session_graph(session_id: str):
    if not _graph_conn:
        return {"nodes": [], "edges": []}
    try:
        return get_session_graph(_graph_conn, session_id)
    except Exception:
        logger.exception("Failed to query session graph for %s", session_id)
        return {"nodes": [], "edges": []}


@app.get("/api/sessions/{session_id}/timeline")
async def session_timeline(session_id: str):
    if not _graph_conn:
        return []
    try:
        return get_session_timeline(_graph_conn, session_id)
    except Exception:
        logger.exception("Failed to query session timeline for %s", session_id)
        return []


# --- NL-to-Cypher endpoints ---


@app.post("/api/ask")
async def ask(request: Request):
    """Translate a natural language question to Cypher, execute it, and return results."""
    if not _anthropic_client:
        return {"error": "ANTHROPIC_API_KEY not configured — NL queries unavailable"}

    body = await request.json()
    question = body.get("question", "")
    if not question:
        return {"error": "Missing 'question' field"}

    try:
        translated = nl_query.translate(question, _anthropic_client)
        cypher = translated["cypher"]
        explanation = translated["explanation"]

        result = _graph_conn.execute(cypher)
        columns = result.get_column_names()
        rows = result.get_all()
        table = [dict(zip(columns, row)) for row in rows]

        return {
            "cypher": cypher,
            "explanation": explanation,
            "result": table,
        }
    except json.JSONDecodeError as e:
        return {"error": "Failed to parse Cypher from AI response", "details": str(e)}
    except Exception as e:
        logger.exception("NL query failed for question: %s", question)
        return {"error": "Query failed", "details": str(e)}


@app.post("/api/cypher")
async def execute_cypher(request: Request):
    """Execute a raw Cypher query against LadybugDB and return results."""
    body = await request.json()
    cypher = body.get("cypher", "")
    if not cypher:
        return {"error": "Missing 'cypher' field"}

    try:
        result = _graph_conn.execute(cypher)
        columns = result.get_column_names()
        rows = result.get_all()
        table = [dict(zip(columns, row)) for row in rows]
        return {"result": table}
    except Exception as e:
        logger.exception("Cypher execution failed: %s", cypher)
        return {"error": "Query execution failed", "cypher": cypher, "details": str(e)}


# --- Replay endpoints ---


@app.post("/api/replay")
async def replay():
    """Rebuild the LadybugDB graph from all DuckDB events."""
    if not _db or not _graph_conn:
        return {"status": "error", "message": "Database not initialized"}

    try:
        reset_graph(_graph_conn)

        rows = _db.execute(
            "SELECT payload FROM events ORDER BY received_at ASC"
        ).fetchall()

        replayed = 0
        errors = 0
        for (payload_json,) in rows:
            event = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
            try:
                materialize_event(_graph_conn, event)
                replayed += 1
            except Exception:
                logger.exception("Replay failed for event")
                errors += 1

        return {
            "status": "ok",
            "events_replayed": replayed,
            "errors": errors,
        }
    except Exception:
        logger.exception("Replay failed")
        return {"status": "error", "message": "Replay failed"}


@app.get("/api/sessions/{session_id}/replay/stream")
async def replay_stream(session_id: str, speed: float = Query(1, ge=0, le=100)):
    """SSE endpoint that replays a session's events with timing proportional to original gaps.

    Touchpoint 4: includes message events interleaved with lifecycle events.
    """
    if not _db:
        return JSONResponse({"error": "Database not initialized"}, status_code=500)

    events_list = get_session_events(_db, session_id)
    if not events_list:
        return JSONResponse({"error": "No events found for session"}, status_code=404)

    # Fetch session messages for interleaving (touchpoint 4)
    messages_list = get_session_messages(_db, session_id, limit=10000)

    total = len(events_list)

    pause_event = asyncio.Event()
    pause_event.set()
    state = {
        "speed": speed,
        "paused": False,
        "position": 0,
        "total": total,
        "pause_event": pause_event,
        "cancelled": False,
    }
    _replay_states[session_id] = state

    async def replay_generator():
        try:
            yield {
                "event": "replay_start",
                "data": json.dumps({
                    "session_id": session_id,
                    "total_events": total,
                    "speed": state["speed"],
                }),
            }

            # Build a merged timeline of events + messages sorted by timestamp
            msg_idx = 0
            prev_ts = None
            for i, row in enumerate(events_list):
                if state["cancelled"]:
                    break

                await state["pause_event"].wait()
                if state["cancelled"]:
                    break

                if i < state["position"]:
                    continue
                state["position"] = i

                received_at = row.get("received_at")
                if prev_ts is not None and received_at is not None and state["speed"] > 0:
                    try:
                        from datetime import datetime
                        if isinstance(received_at, str):
                            curr = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
                        else:
                            curr = received_at
                        if isinstance(prev_ts, str):
                            prev = datetime.fromisoformat(prev_ts.replace("Z", "+00:00"))
                        else:
                            prev = prev_ts

                        gap_seconds = (curr - prev).total_seconds()
                        if gap_seconds > 0:
                            delay = gap_seconds / state["speed"]
                            delay = min(delay, 5.0)
                            await asyncio.sleep(delay)
                    except (ValueError, TypeError):
                        pass

                prev_ts = received_at

                payload_raw = row.get("payload")
                if isinstance(payload_raw, str):
                    payload_data = json.loads(payload_raw)
                else:
                    payload_data = payload_raw or {}

                event_type = row.get("event_type", "unknown")

                sse_data = json.dumps({
                    "event_id": row.get("event_id"),
                    "replay_position": i,
                    "replay_total": total,
                    **payload_data,
                })
                yield {"event": event_type, "data": sse_data}

                # Emit any messages whose timestamp falls before the next event (touchpoint 4)
                while msg_idx < len(messages_list):
                    msg = messages_list[msg_idx]
                    msg_ts = msg.get("timestamp")
                    # Check if next event has a later timestamp
                    next_event_ts = events_list[i + 1].get("received_at") if i + 1 < total else None
                    if next_event_ts is not None and msg_ts is not None:
                        try:
                            if isinstance(msg_ts, str):
                                mt = datetime.fromisoformat(msg_ts.replace("Z", "+00:00"))
                            else:
                                mt = msg_ts
                            if isinstance(next_event_ts, str):
                                nt = datetime.fromisoformat(next_event_ts.replace("Z", "+00:00"))
                            else:
                                nt = next_event_ts
                            if mt >= nt:
                                break
                        except (ValueError, TypeError):
                            break
                    elif next_event_ts is not None:
                        break

                    msg_data = json.dumps({
                        "message_id": msg.get("message_id"),
                        "agent_id": msg.get("agent_id"),
                        "session_id": msg.get("session_id"),
                        "role": msg.get("role"),
                        "sequence": msg.get("sequence"),
                        "synthetic": msg.get("synthetic", False),
                        "content_preview": msg.get("content_preview", ""),
                        "replay_position": i,
                        "replay_total": total,
                    })
                    yield {"event": "message", "data": msg_data}
                    msg_idx += 1

            yield {
                "event": "replay_end",
                "data": json.dumps({
                    "session_id": session_id,
                    "total_events": total,
                }),
            }
        finally:
            _replay_states.pop(session_id, None)

    return EventSourceResponse(replay_generator())


@app.post("/api/sessions/{session_id}/replay/control")
async def replay_control(session_id: str, request: Request):
    """Control an active replay: pause, resume, seek, speed, or stop."""
    state = _replay_states.get(session_id)
    if not state:
        return JSONResponse({"error": "No active replay for this session"}, status_code=404)

    body = await request.json()
    action = body.get("action")

    if action == "pause":
        state["paused"] = True
        state["pause_event"].clear()
        return {"status": "paused", "position": state["position"]}

    elif action == "resume":
        state["paused"] = False
        state["pause_event"].set()
        return {"status": "playing", "position": state["position"]}

    elif action == "seek":
        position = body.get("position", 0)
        if not isinstance(position, int) or position < 0 or position >= state["total"]:
            return JSONResponse({"error": "Invalid position"}, status_code=400)
        state["position"] = position
        return {"status": "paused" if state["paused"] else "playing", "position": position}

    elif action == "speed":
        speed = body.get("speed", 1)
        if not isinstance(speed, (int, float)) or speed < 0:
            return JSONResponse({"error": "Invalid speed"}, status_code=400)
        state["speed"] = speed
        return {"status": "ok", "speed": speed}

    elif action == "stop":
        state["cancelled"] = True
        state["pause_event"].set()
        return {"status": "stopped"}

    else:
        return JSONResponse({"error": f"Unknown action: {action}"}, status_code=400)


@app.get("/api/sessions/{session_id}/replay/status")
async def replay_status(session_id: str):
    """Get current replay state for a session."""
    state = _replay_states.get(session_id)
    if not state:
        return {"active": False}
    return {
        "active": True,
        "paused": state["paused"],
        "position": state["position"],
        "total": state["total"],
        "speed": state["speed"],
    }
