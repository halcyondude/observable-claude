import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from anthropic import Anthropic

from .ledger import (
    init_db, write_event, query_events, get_sessions, get_active_sessions,
    get_session_events, get_session_event_count,
)
from .graph import init_graph, materialize_event, get_session_graph, get_session_timeline, reset_graph
from . import nl_query

logger = logging.getLogger(__name__)

_start_time: float = 0.0
_db = None
_graph_conn = None
_graph_db = None
_anthropic_client = None
_sse_clients: list[asyncio.Queue] = []

# Replay state: keyed by session_id
# Each entry: {"speed": float, "paused": bool, "position": int, "total": int, "event": asyncio.Event}
_replay_states: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _db, _graph_db, _graph_conn, _anthropic_client, _start_time
    db_path = os.environ.get("DUCKDB_PATH", "./data/duckdb/events.db")
    ladybug_path = os.environ.get("LADYBUG_PATH", "./data/ladybug")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    # LadybugDB creates the database directory itself — only ensure parent exists
    os.makedirs(os.path.dirname(ladybug_path) or ".", exist_ok=True)
    _db = init_db(db_path)
    _graph_db, _graph_conn = init_graph(ladybug_path)
    _start_time = time.time()

    # Initialize Anthropic client for NL->Cypher (uses ANTHROPIC_API_KEY from env)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        _anthropic_client = Anthropic()
    else:
        logger.warning("ANTHROPIC_API_KEY not set — /api/ask endpoint will be unavailable")

    yield
    if _db:
        _db.close()


app = FastAPI(lifespan=lifespan)


@app.post("/events")
async def ingest_event(request: Request):
    payload = await request.json()
    event_id = write_event(_db, payload)

    # Graph materialization — best-effort, never blocks event ingestion
    if _graph_conn:
        try:
            materialize_event(_graph_conn, payload)
        except Exception:
            logger.exception("Graph materialization failed for event %s", event_id)

    event_type = payload.get("event", {}).get("event_type", payload.get("event_type", "unknown"))
    sse_data = json.dumps({"event_id": event_id, **payload})

    dead = []
    for q in _sse_clients:
        try:
            q.put_nowait((event_type, sse_data))
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _sse_clients.remove(q)

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


@app.get("/api/sessions")
async def list_sessions():
    return get_sessions(_db)


@app.get("/api/sessions/active")
async def list_active_sessions():
    return get_active_sessions(_db)


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
    """SSE endpoint that replays a session's events with timing proportional to original gaps."""
    if not _db:
        return JSONResponse({"error": "Database not initialized"}, status_code=500)

    events_list = get_session_events(_db, session_id)
    if not events_list:
        return JSONResponse({"error": "No events found for session"}, status_code=404)

    total = len(events_list)

    # Initialize replay state
    pause_event = asyncio.Event()
    pause_event.set()  # Start unpaused
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
            # Emit metadata as first event
            yield {
                "event": "replay_start",
                "data": json.dumps({
                    "session_id": session_id,
                    "total_events": total,
                    "speed": state["speed"],
                }),
            }

            prev_ts = None
            for i, row in enumerate(events_list):
                if state["cancelled"]:
                    break

                # Wait if paused
                await state["pause_event"].wait()

                if state["cancelled"]:
                    break

                # Handle seek: if position jumped ahead, skip
                if i < state["position"]:
                    continue

                state["position"] = i

                # Calculate delay based on inter-event gap
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
                            # Cap individual delays at 5 seconds to keep replay responsive
                            delay = min(delay, 5.0)
                            await asyncio.sleep(delay)
                    except (ValueError, TypeError):
                        pass

                prev_ts = received_at

                # Parse payload and emit as SSE event
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

            # Emit completion event
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
    """Control an active replay: pause, resume, seek, or stop."""
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
        # If paused, stay paused at new position
        return {"status": "paused" if state["paused"] else "playing", "position": position}

    elif action == "speed":
        speed = body.get("speed", 1)
        if not isinstance(speed, (int, float)) or speed < 0:
            return JSONResponse({"error": "Invalid speed"}, status_code=400)
        state["speed"] = speed
        return {"status": "ok", "speed": speed}

    elif action == "stop":
        state["cancelled"] = True
        state["pause_event"].set()  # Unblock if paused so generator can exit
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
