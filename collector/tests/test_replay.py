"""Tests for the session replay SSE endpoint and control API."""

import asyncio
import json
import os
import tempfile

import pytest
from httpx import AsyncClient, ASGITransport

# Patch env before importing collector
# LadybugDB path must not exist yet (it creates the db there)
_tmp_dir = tempfile.mkdtemp()
os.environ["LADYBUG_PATH"] = os.path.join(_tmp_dir, "test_graph")

from collector.collector import app, _replay_states


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    """Initialize the collector with a temp DuckDB and seed test events."""
    db_path = str(tmp_path / "test.db")
    os.environ["DUCKDB_PATH"] = db_path
    # LadybugDB needs a path that doesn't exist yet — it creates the db files there
    # The parent dir must exist, but the path itself must not be a directory
    ladybug_path = str(tmp_path / "ladybug" / "graph.db")
    os.makedirs(str(tmp_path / "ladybug"), exist_ok=True)
    os.environ["LADYBUG_PATH"] = ladybug_path

    async with app.router.lifespan_context(app):
        # Seed events via the ingest endpoint
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for i in range(5):
                event = {
                    "session": {"session_id": "test-session-1", "agent_id": f"agent-{i}"},
                    "event": {"event_type": "SubagentStart" if i % 2 == 0 else "PreToolUse"},
                }
                resp = await client.post("/events", json=event)
                assert resp.status_code == 200
                # Small delay so received_at timestamps differ
                await asyncio.sleep(0.01)

        yield


@pytest.mark.anyio
async def test_replay_stream_returns_events():
    """Replay stream emits all session events as SSE."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Use speed=0 for max speed (no delays)
        resp = await client.get(
            "/api/sessions/test-session-1/replay/stream?speed=0",
            timeout=10,
        )
        assert resp.status_code == 200


@pytest.mark.anyio
async def test_replay_stream_404_for_unknown_session():
    """Replay stream returns 404 for a session with no events."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/sessions/nonexistent/replay/stream?speed=0")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_replay_control_no_active_replay():
    """Control endpoint returns 404 when no replay is active."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/sessions/test-session-1/replay/control",
            json={"action": "pause"},
        )
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_replay_control_unknown_action():
    """Control endpoint rejects unknown actions."""
    # Manually create a replay state entry to test control
    pause_event = asyncio.Event()
    pause_event.set()
    _replay_states["test-session-1"] = {
        "speed": 1,
        "paused": False,
        "position": 0,
        "total": 5,
        "pause_event": pause_event,
        "cancelled": False,
    }

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/sessions/test-session-1/replay/control",
                json={"action": "explode"},
            )
            assert resp.status_code == 400
    finally:
        _replay_states.pop("test-session-1", None)


@pytest.mark.anyio
async def test_replay_control_pause_resume():
    """Control endpoint can pause and resume a replay."""
    pause_event = asyncio.Event()
    pause_event.set()
    _replay_states["test-session-1"] = {
        "speed": 1,
        "paused": False,
        "position": 2,
        "total": 5,
        "pause_event": pause_event,
        "cancelled": False,
    }

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Pause
            resp = await client.post(
                "/api/sessions/test-session-1/replay/control",
                json={"action": "pause"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "paused"
            assert _replay_states["test-session-1"]["paused"] is True

            # Resume
            resp = await client.post(
                "/api/sessions/test-session-1/replay/control",
                json={"action": "resume"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "playing"
            assert _replay_states["test-session-1"]["paused"] is False
    finally:
        _replay_states.pop("test-session-1", None)


@pytest.mark.anyio
async def test_replay_control_speed():
    """Control endpoint can change replay speed."""
    pause_event = asyncio.Event()
    pause_event.set()
    _replay_states["test-session-1"] = {
        "speed": 1,
        "paused": False,
        "position": 0,
        "total": 5,
        "pause_event": pause_event,
        "cancelled": False,
    }

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/sessions/test-session-1/replay/control",
                json={"action": "speed", "speed": 10},
            )
            assert resp.status_code == 200
            assert _replay_states["test-session-1"]["speed"] == 10
    finally:
        _replay_states.pop("test-session-1", None)


@pytest.mark.anyio
async def test_replay_control_seek():
    """Control endpoint can seek to a position."""
    pause_event = asyncio.Event()
    pause_event.set()
    _replay_states["test-session-1"] = {
        "speed": 1,
        "paused": False,
        "position": 0,
        "total": 5,
        "pause_event": pause_event,
        "cancelled": False,
    }

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/sessions/test-session-1/replay/control",
                json={"action": "seek", "position": 3},
            )
            assert resp.status_code == 200
            assert _replay_states["test-session-1"]["position"] == 3
    finally:
        _replay_states.pop("test-session-1", None)


@pytest.mark.anyio
async def test_replay_status_inactive():
    """Status endpoint returns active=False when no replay is running."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/sessions/test-session-1/replay/status")
        assert resp.status_code == 200
        assert resp.json()["active"] is False


@pytest.mark.anyio
async def test_replay_status_active():
    """Status endpoint returns state when a replay is running."""
    pause_event = asyncio.Event()
    pause_event.set()
    _replay_states["test-session-1"] = {
        "speed": 5,
        "paused": True,
        "position": 3,
        "total": 10,
        "pause_event": pause_event,
        "cancelled": False,
    }

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/sessions/test-session-1/replay/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["active"] is True
            assert data["paused"] is True
            assert data["position"] == 3
            assert data["total"] == 10
            assert data["speed"] == 5
    finally:
        _replay_states.pop("test-session-1", None)


@pytest.mark.anyio
async def test_ledger_get_session_events():
    """get_session_events returns events in chronological order."""
    from collector.collector import _db
    from collector.ledger import get_session_events

    events = get_session_events(_db, "test-session-1")
    assert len(events) == 5
    # Verify chronological ordering
    for i in range(1, len(events)):
        assert events[i]["received_at"] >= events[i - 1]["received_at"]


@pytest.mark.anyio
async def test_ledger_get_session_event_count():
    """get_session_event_count returns correct count."""
    from collector.collector import _db
    from collector.ledger import get_session_event_count

    count = get_session_event_count(_db, "test-session-1")
    assert count == 5

    count_empty = get_session_event_count(_db, "nonexistent")
    assert count_empty == 0
