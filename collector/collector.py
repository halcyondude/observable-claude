import asyncio
import os
import time
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .ledger import init_db, write_event, query_events, get_sessions, get_active_sessions


_start_time: float = 0.0
_db = None
_sse_clients: list[asyncio.Queue] = []


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _db, _start_time
    db_path = os.environ.get("DUCKDB_PATH", "./data/duckdb/events.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    _db = init_db(db_path)
    _start_time = time.time()
    yield
    if _db:
        _db.close()


app = FastAPI(lifespan=lifespan)


@app.post("/events")
async def ingest_event(request: Request):
    payload = await request.json()
    event_id = write_event(_db, payload)

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
