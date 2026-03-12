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
    init_db,
    write_event,
    query_events,
    get_sessions,
    get_active_sessions,
    write_message,
    get_agent_messages,
    search_messages,
    get_session_messages,
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


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _db, _graph_db, _graph_conn, _anthropic_client, _start_time
    db_path = os.environ.get("DUCKDB_PATH", "./data/duckdb/events.db")
    ladybug_path = os.environ.get("LADYBUG_PATH", "./data/ladybug")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(ladybug_path, exist_ok=True)
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
            _db,
            q=q,
            session_id=session_id,
            agent_id=agent_id,
            role=role,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.exception("Message search failed for q=%s", q)
        return JSONResponse(
            status_code=400,
            content={"error": "Search failed", "details": str(e)},
        )


@app.get("/api/agents/{agent_id}/messages")
async def agent_messages(agent_id: str):
    """Get all messages for a specific agent."""
    return get_agent_messages(_db, agent_id)


@app.get("/api/sessions/{session_id}/messages")
async def session_messages(
    session_id: str,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get all messages across all agents in a session."""
    return get_session_messages(_db, session_id, limit=limit, offset=offset)


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
