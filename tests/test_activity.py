"""Tests for the activity histogram and session summary features."""

import json
from datetime import datetime, timedelta, timezone

import duckdb
import pytest

from collector.ledger import (
    init_db,
    write_event,
    get_activity_histogram,
    get_session_summary,
)


@pytest.fixture
def db():
    """In-memory DuckDB with schema initialized."""
    conn = init_db(":memory:")
    yield conn
    conn.close()


def _make_event(session_id, event_type="ToolUse", cwd="/workspace/a", ts=None):
    """Build a minimal event payload matching the collector's expected shape."""
    return {
        "session": {"session_id": session_id, "cwd": cwd},
        "event": {"event_type": event_type},
    }


def _insert_event_at(conn, session_id, event_type, cwd, ts):
    """Insert an event and backdate it to a specific timestamp."""
    event_id = write_event(conn, _make_event(session_id, event_type, cwd))
    conn.execute(
        "UPDATE events SET received_at = ? WHERE event_id = ?",
        [ts, event_id],
    )
    return event_id


class TestGetActivityHistogram:
    def test_empty_table_returns_empty(self, db):
        result = get_activity_histogram(db)
        assert result == []

    def test_single_event_returns_one_bucket(self, db):
        write_event(db, _make_event("s1"))
        result = get_activity_histogram(db, bucket_seconds=60)
        assert len(result) == 1
        assert result[0]["count"] == 1
        assert result[0]["cwd"] == "/workspace/a"
        assert "timestamp" in result[0]

    def test_groups_by_cwd(self, db):
        now = datetime.now(timezone.utc)
        _insert_event_at(db, "s1", "ToolUse", "/workspace/a", now)
        _insert_event_at(db, "s2", "ToolUse", "/workspace/b", now)
        _insert_event_at(db, "s1", "ToolUse", "/workspace/a", now + timedelta(seconds=1))

        result = get_activity_histogram(db, bucket_seconds=3600)
        # Two cwd groups in one time bucket
        assert len(result) == 2
        by_cwd = {r["cwd"]: r["count"] for r in result}
        assert by_cwd["/workspace/a"] == 2
        assert by_cwd["/workspace/b"] == 1

    def test_multiple_buckets(self, db):
        t0 = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)
        t1 = t0 + timedelta(minutes=5)

        _insert_event_at(db, "s1", "ToolUse", "/workspace/a", t0)
        _insert_event_at(db, "s1", "ToolUse", "/workspace/a", t0 + timedelta(seconds=10))
        _insert_event_at(db, "s1", "ToolUse", "/workspace/a", t1)

        result = get_activity_histogram(db, bucket_seconds=60)
        assert len(result) == 2
        assert result[0]["count"] == 2
        assert result[1]["count"] == 1

    def test_since_filter(self, db):
        t0 = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)
        t1 = t0 + timedelta(hours=1)
        cutoff = t0 + timedelta(minutes=30)

        _insert_event_at(db, "s1", "ToolUse", "/workspace/a", t0)
        _insert_event_at(db, "s1", "ToolUse", "/workspace/a", t1)

        result = get_activity_histogram(db, since=cutoff.isoformat())
        assert len(result) == 1
        assert result[0]["count"] == 1

    def test_until_filter(self, db):
        t0 = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)
        t1 = t0 + timedelta(hours=1)
        cutoff = t0 + timedelta(minutes=30)

        _insert_event_at(db, "s1", "ToolUse", "/workspace/a", t0)
        _insert_event_at(db, "s1", "ToolUse", "/workspace/a", t1)

        result = get_activity_histogram(db, until=cutoff.isoformat())
        assert len(result) == 1
        assert result[0]["count"] == 1

    def test_ordered_by_timestamp_asc(self, db):
        t0 = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)
        # Insert later event first
        _insert_event_at(db, "s1", "ToolUse", "/workspace/a", t0 + timedelta(hours=1))
        _insert_event_at(db, "s1", "ToolUse", "/workspace/a", t0)

        result = get_activity_histogram(db, bucket_seconds=60)
        assert result[0]["timestamp"] < result[1]["timestamp"]

    def test_custom_bucket_size(self, db):
        t0 = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)
        # 3 events across 2 minutes — with 120s buckets, should be 1 bucket
        for i in range(3):
            _insert_event_at(db, "s1", "ToolUse", "/workspace/a", t0 + timedelta(seconds=i * 30))

        result_narrow = get_activity_histogram(db, bucket_seconds=30)
        result_wide = get_activity_histogram(db, bucket_seconds=120)
        assert len(result_wide) == 1
        assert result_wide[0]["count"] == 3
        assert len(result_narrow) >= 2


class TestGetSessionSummary:
    def test_empty_table(self, db):
        result = get_session_summary(db)
        assert result == {"total": 0, "active": 0, "workspaces": 0}

    def test_counts_sessions_and_workspaces(self, db):
        write_event(db, _make_event("s1", "SessionStart", "/workspace/a"))
        write_event(db, _make_event("s2", "SessionStart", "/workspace/b"))
        write_event(db, _make_event("s1", "ToolUse", "/workspace/a"))

        result = get_session_summary(db)
        assert result["total"] == 2
        assert result["active"] == 2
        assert result["workspaces"] == 2

    def test_completed_session_not_active(self, db):
        write_event(db, _make_event("s1", "SessionStart", "/workspace/a"))
        write_event(db, _make_event("s1", "SessionEnd", "/workspace/a"))
        write_event(db, _make_event("s2", "SessionStart", "/workspace/b"))

        result = get_session_summary(db)
        assert result["total"] == 2
        assert result["active"] == 1

    def test_no_session_start_means_not_active(self, db):
        # Events without SessionStart shouldn't count as active
        write_event(db, _make_event("s1", "ToolUse", "/workspace/a"))

        result = get_session_summary(db)
        assert result["total"] == 1
        assert result["active"] == 0
