"""Tests for session save/bookmark functionality."""
import json
import tempfile
import os

import duckdb
import pytest

from collector.ledger import (
    init_db,
    write_event,
    get_sessions,
    get_active_sessions,
    save_session,
    unsave_session,
    get_saved_sessions,
    update_saved_session,
)


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.db")
        conn = init_db(path)
        yield conn
        conn.close()


def _make_event(session_id, event_type="ToolUse", agent_id="agent-1"):
    return {
        "event": {"event_type": event_type},
        "session": {"session_id": session_id, "agent_id": agent_id, "cwd": "/tmp"},
    }


def _seed_session(db, session_id="sess-1", n_events=5, n_agents=2):
    for i in range(n_events):
        agent = f"agent-{i % n_agents}"
        write_event(db, _make_event(session_id, agent_id=agent))


class TestSavedSessionsTable:
    def test_table_created(self, db):
        tables = db.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'saved_sessions'"
        ).fetchall()
        assert len(tables) == 1

    def test_save_session(self, db):
        _seed_session(db, "sess-1", n_events=5, n_agents=2)
        result = save_session(db, "sess-1", "My Session", "some notes", "debug,test")

        assert result["session_id"] == "sess-1"
        assert result["name"] == "My Session"
        assert result["notes"] == "some notes"
        assert result["tags"] == "debug,test"
        assert result["event_count"] == 5
        assert result["agent_count"] == 2
        assert result["duration_seconds"] is not None
        assert result["saved_at"] is not None

    def test_save_session_duplicate_fails(self, db):
        _seed_session(db, "sess-1")
        save_session(db, "sess-1", "First save")
        with pytest.raises(Exception):
            save_session(db, "sess-1", "Duplicate save")

    def test_unsave_session(self, db):
        _seed_session(db, "sess-1")
        save_session(db, "sess-1", "To delete")
        unsave_session(db, "sess-1")
        assert get_saved_sessions(db) == []

    def test_get_saved_sessions(self, db):
        _seed_session(db, "sess-1")
        _seed_session(db, "sess-2")
        save_session(db, "sess-1", "First")
        save_session(db, "sess-2", "Second")
        saved = get_saved_sessions(db)
        assert len(saved) == 2
        names = {s["name"] for s in saved}
        assert names == {"First", "Second"}

    def test_update_saved_session(self, db):
        _seed_session(db, "sess-1")
        save_session(db, "sess-1", "Original", "old notes", "tag1")

        result = update_saved_session(db, "sess-1", name="Updated", notes="new notes", tags="tag2")
        assert result["name"] == "Updated"
        assert result["notes"] == "new notes"
        assert result["tags"] == "tag2"

    def test_update_partial_fields(self, db):
        _seed_session(db, "sess-1")
        save_session(db, "sess-1", "Original", "old notes", "tag1")

        result = update_saved_session(db, "sess-1", name="Updated")
        assert result["name"] == "Updated"
        assert result["notes"] == "old notes"
        assert result["tags"] == "tag1"

    def test_update_nonexistent_returns_none(self, db):
        result = update_saved_session(db, "no-such-session", name="Nope")
        assert result is None


class TestSessionsWithSavedFlag:
    def test_get_sessions_includes_saved_field(self, db):
        _seed_session(db, "sess-1")
        _seed_session(db, "sess-2")
        save_session(db, "sess-1", "Saved one")

        sessions = get_sessions(db)
        by_id = {s["session_id"]: s for s in sessions}
        assert by_id["sess-1"]["saved"] is True
        assert by_id["sess-2"]["saved"] is False

    def test_get_active_sessions_includes_saved_field(self, db):
        write_event(db, _make_event("sess-1", event_type="SessionStart"))
        save_session(db, "sess-1", "Active saved")

        active = get_active_sessions(db)
        assert len(active) == 1
        assert active[0]["saved"] is True
