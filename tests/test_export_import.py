"""Tests for .ccobs session export/import functionality."""

import gzip
import json
import uuid

import duckdb
import pytest

from collector.ledger import (
    CCOBS_VERSION,
    export_session,
    export_session_gzip,
    import_session,
    init_db,
    parse_ccobs,
    write_event,
)


@pytest.fixture
def db(tmp_path):
    """Create an in-memory DuckDB with the schema initialized."""
    conn = init_db(str(tmp_path / "test.db"))
    yield conn
    conn.close()


def _make_event(session_id: str, event_type: str = "PreToolUse", **overrides) -> dict:
    """Build a minimal event payload matching the hook format."""
    return {
        "session": {
            "session_id": session_id,
            "agent_id": overrides.get("agent_id", "agent-1"),
            "agent_type": overrides.get("agent_type", "main"),
            "cwd": overrides.get("cwd", "/tmp/test"),
        },
        "event": {
            "event_type": event_type,
            "tool_use_id": overrides.get("tool_use_id", str(uuid.uuid4())),
            "tool_name": overrides.get("tool_name", "Bash"),
        },
    }


def _seed_session(db, session_id: str, event_count: int = 5) -> list[str]:
    """Insert a session's worth of events, return their event_ids."""
    ids = []
    ids.append(write_event(db, _make_event(session_id, "SessionStart")))
    for i in range(event_count - 2):
        ids.append(write_event(db, _make_event(session_id, "PreToolUse", tool_name=f"Tool{i}")))
    ids.append(write_event(db, _make_event(session_id, "SessionEnd")))
    return ids


class TestExportSession:
    def test_export_basic_structure(self, db):
        sid = "sess-export-1"
        _seed_session(db, sid, event_count=4)

        result = export_session(db, sid, {"nodes": [], "edges": []}, [])

        assert result["version"] == CCOBS_VERSION
        assert result["session"]["session_id"] == sid
        assert result["exported_at"]
        assert len(result["events"]) == 4
        assert result["stats"]["event_count"] == 4
        assert result["graph"] == {"nodes": [], "edges": []}
        assert result["timeline"] == []

    def test_export_includes_stats(self, db):
        sid = "sess-export-stats"
        _seed_session(db, sid, event_count=6)

        result = export_session(db, sid, {"nodes": [], "edges": []}, [])

        assert result["stats"]["event_count"] == 6
        # 4 PreToolUse events (6 total minus SessionStart and SessionEnd)
        assert result["stats"]["tool_calls"] == 4
        assert result["stats"]["agent_count"] == 1

    def test_export_with_saved_metadata(self, db):
        sid = "sess-export-saved"
        _seed_session(db, sid, event_count=3)

        db.execute(
            "INSERT INTO saved_sessions (session_id, name, notes, tags) VALUES (?, ?, ?, ?)",
            [sid, "My Session", "Some notes", '["debug"]'],
        )

        result = export_session(db, sid, {"nodes": [], "edges": []}, [])

        assert result["session"]["name"] == "My Session"
        assert result["session"]["notes"] == "Some notes"
        assert result["session"]["tags"] == ["debug"]

        # export_count should be incremented
        count = db.execute(
            "SELECT export_count FROM saved_sessions WHERE session_id = ?", [sid]
        ).fetchone()[0]
        assert count == 1

    def test_export_nonexistent_session_raises(self, db):
        with pytest.raises(ValueError, match="No events found"):
            export_session(db, "nonexistent", {}, [])

    def test_export_events_chronological(self, db):
        sid = "sess-export-order"
        _seed_session(db, sid, event_count=5)

        result = export_session(db, sid, {"nodes": [], "edges": []}, [])
        events = result["events"]

        # First should be SessionStart, last should be SessionEnd
        assert events[0]["event_type"] == "SessionStart"
        assert events[-1]["event_type"] == "SessionEnd"


class TestExportSessionGzip:
    def test_produces_valid_gzip(self, db):
        sid = "sess-gz"
        _seed_session(db, sid, event_count=3)

        gz_bytes = export_session_gzip(db, sid, {"nodes": [], "edges": []}, [])

        assert isinstance(gz_bytes, bytes)
        decompressed = gzip.decompress(gz_bytes)
        data = json.loads(decompressed)
        assert data["version"] == CCOBS_VERSION
        assert data["session"]["session_id"] == sid


class TestImportSession:
    def _make_ccobs(self, session_id: str, events: list[dict] | None = None) -> dict:
        if events is None:
            events = [
                {
                    "event_id": str(uuid.uuid4()),
                    "received_at": "2026-03-12T10:00:00+00:00",
                    "event_type": "SessionStart",
                    "session_id": session_id,
                    "agent_id": "agent-1",
                    "agent_type": "main",
                    "tool_use_id": None,
                    "tool_name": None,
                    "cwd": "/tmp",
                    "payload": "{}",
                },
                {
                    "event_id": str(uuid.uuid4()),
                    "received_at": "2026-03-12T10:01:00+00:00",
                    "event_type": "SessionEnd",
                    "session_id": session_id,
                    "agent_id": "agent-1",
                    "agent_type": "main",
                    "tool_use_id": None,
                    "tool_name": None,
                    "cwd": "/tmp",
                    "payload": "{}",
                },
            ]
        return {
            "version": CCOBS_VERSION,
            "exported_at": "2026-03-12T12:00:00+00:00",
            "session": {
                "session_id": session_id,
                "cwd": "/tmp",
                "start_ts": "2026-03-12T10:00:00+00:00",
                "end_ts": "2026-03-12T10:01:00+00:00",
                "name": "Test Import",
                "notes": "test notes",
                "tags": ["test"],
            },
            "events": events,
            "graph": {"nodes": [], "edges": []},
            "timeline": [],
            "stats": {"event_count": len(events), "agent_count": 1, "duration_seconds": 60, "tool_calls": 0},
        }

    def test_import_fresh(self, db):
        sid = "sess-import-1"
        data = self._make_ccobs(sid)

        result = import_session(db, data)

        assert result["imported"] == 2
        assert result["skipped"] == 0
        assert result["session_id"] == sid

        # Events should be in DuckDB
        count = db.execute("SELECT COUNT(*) FROM events WHERE session_id = ?", [sid]).fetchone()[0]
        assert count == 2

        # Should be in saved_sessions
        saved = db.execute("SELECT name, notes, tags FROM saved_sessions WHERE session_id = ?", [sid]).fetchone()
        assert saved[0] == "Test Import"
        assert saved[1] == "test notes"

    def test_import_deduplicates(self, db):
        sid = "sess-import-dedup"
        data = self._make_ccobs(sid)

        # Import twice
        r1 = import_session(db, data)
        r2 = import_session(db, data)

        assert r1["imported"] == 2
        assert r2["imported"] == 0
        assert r2["skipped"] == 2

        count = db.execute("SELECT COUNT(*) FROM events WHERE session_id = ?", [sid]).fetchone()[0]
        assert count == 2

    def test_import_rejects_bad_version(self, db):
        data = {"version": 999, "session": {"session_id": "x"}, "events": []}
        with pytest.raises(ValueError, match="Unsupported .ccobs version"):
            import_session(db, data)

    def test_import_rejects_missing_session_id(self, db):
        data = {"version": CCOBS_VERSION, "session": {}, "events": []}
        with pytest.raises(ValueError, match="Missing session_id"):
            import_session(db, data)

    def test_import_skips_events_without_id(self, db):
        sid = "sess-import-noid"
        data = self._make_ccobs(sid, events=[
            {"event_type": "SessionStart", "session_id": sid},  # no event_id
        ])

        result = import_session(db, data)
        assert result["imported"] == 0
        assert result["skipped"] == 1

    def test_import_uses_default_name(self, db):
        sid = "sess-import-noname"
        data = self._make_ccobs(sid)
        del data["session"]["name"]

        import_session(db, data)

        saved = db.execute("SELECT name FROM saved_sessions WHERE session_id = ?", [sid]).fetchone()
        assert saved[0].startswith("Imported:")


class TestParseCcobs:
    def test_parse_gzipped(self):
        original = {"version": 1, "test": True}
        gz = gzip.compress(json.dumps(original).encode())
        assert parse_ccobs(gz) == original

    def test_parse_plain_json(self):
        original = {"version": 1, "test": True}
        raw = json.dumps(original).encode()
        assert parse_ccobs(raw) == original

    def test_parse_invalid_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_ccobs(b"not json at all")


class TestRoundTrip:
    """End-to-end: seed a session, export it, import into a fresh DB."""

    def test_full_roundtrip(self, tmp_path):
        # Set up source DB with a session
        src = init_db(str(tmp_path / "src.db"))
        sid = "sess-roundtrip"
        _seed_session(src, sid, event_count=5)

        # Export
        exported = export_session(src, sid, {"nodes": [{"data": {"id": "n1"}}], "edges": []}, [{"agent_id": "a1"}])
        gz = gzip.compress(json.dumps(exported, default=str).encode())

        # Import into a fresh DB
        dst = init_db(str(tmp_path / "dst.db"))
        parsed = parse_ccobs(gz)
        result = import_session(dst, parsed)

        assert result["imported"] == 5
        assert result["session_id"] == sid

        # Verify events round-tripped
        count = dst.execute("SELECT COUNT(*) FROM events WHERE session_id = ?", [sid]).fetchone()[0]
        assert count == 5

        src.close()
        dst.close()
