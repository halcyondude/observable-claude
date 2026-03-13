import json

import pytest
from fastapi.testclient import TestClient

from collector.collector import app, _db, _sse_clients
from collector import collector as collector_mod
from collector.ledger import init_db


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    collector_mod._db = init_db(db_path)
    collector_mod._graph_conn = None
    collector_mod._graph_db = None
    yield
    if collector_mod._db:
        collector_mod._db.close()
        collector_mod._db = None


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def _subagent_start_event(agent_id="agent-1", session_id="sess-1", prompt="do the thing"):
    return {
        "event": {
            "event_type": "SubagentStart",
            "prompt": prompt,
            "parent_agent_id": "parent-1",
            "timestamp": "2025-01-01T00:00:00Z",
        },
        "session": {
            "session_id": session_id,
            "agent_id": agent_id,
            "agent_type": "subagent",
        },
    }


def test_subagent_start_captures_prompt(client):
    resp = client.post("/events", json=_subagent_start_event())
    assert resp.status_code == 200

    resp = client.get("/api/agents/agent-1/messages")
    assert resp.status_code == 200
    msgs = resp.json()
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "do the thing"
    assert msgs[0]["sequence"] == 0


def test_subagent_start_no_prompt_no_message(client):
    event = _subagent_start_event(prompt=None)
    event["event"].pop("prompt")
    client.post("/events", json=event)

    resp = client.get("/api/agents/agent-1/messages")
    assert resp.json() == []


def test_messages_search_endpoint(client):
    client.post("/events", json=_subagent_start_event(prompt="implement error handling"))
    client.post("/events", json=_subagent_start_event(
        agent_id="agent-2", prompt="write unit tests"
    ))

    resp = client.get("/api/messages/search", params={"q": "error"})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["agent_id"] == "agent-1"


def test_messages_search_with_session_filter(client):
    client.post("/events", json=_subagent_start_event(
        agent_id="a1", session_id="s1", prompt="fix the bug"
    ))
    client.post("/events", json=_subagent_start_event(
        agent_id="a2", session_id="s2", prompt="fix the bug"
    ))

    resp = client.get("/api/messages/search", params={"q": "bug", "session_id": "s1"})
    results = resp.json()
    assert len(results) == 1
    assert results[0]["session_id"] == "s1"


def test_messages_search_requires_query(client):
    resp = client.get("/api/messages/search")
    assert resp.status_code == 422


def test_agent_messages_empty(client):
    resp = client.get("/api/agents/nonexistent/messages")
    assert resp.status_code == 200
    assert resp.json() == []


def test_flat_payload_format(client):
    """SubagentStart with flat (non-nested) payload fields should also work."""
    event = {
        "event_type": "SubagentStart",
        "prompt": "flat format prompt",
        "session_id": "sess-flat",
        "agent_id": "agent-flat",
        "agent_type": "subagent",
        "timestamp": "2025-01-01T00:00:00Z",
    }
    client.post("/events", json=event)

    resp = client.get("/api/agents/agent-flat/messages")
    msgs = resp.json()
    assert len(msgs) == 1
    assert msgs[0]["content"] == "flat format prompt"
