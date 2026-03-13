"""Tests for message capture and inference (issue #8)."""
import json
import pytest
import duckdb

from collector.ledger import (
    init_db,
    write_event,
    write_message,
    get_next_sequence,
    get_agent_messages,
    get_session_messages,
    get_agent_tool_summary,
)


@pytest.fixture
def db():
    """In-memory DuckDB for testing."""
    conn = init_db(":memory:")
    yield conn
    conn.close()


class TestMessagesTable:
    def test_write_message_basic(self, db):
        msg_id = write_message(
            db,
            session_id="s1",
            agent_id="a1",
            role="user",
            content="Hello world",
        )
        assert msg_id is not None
        rows = db.execute("SELECT * FROM messages WHERE message_id = ?", [msg_id]).fetchall()
        assert len(rows) == 1

    def test_write_message_synthetic(self, db):
        msg_id = write_message(
            db,
            session_id="s1",
            agent_id="a1",
            role="assistant",
            content="Synthetic response",
            synthetic=True,
        )
        row = db.execute(
            "SELECT synthetic FROM messages WHERE message_id = ?", [msg_id]
        ).fetchone()
        assert row[0] is True

    def test_write_message_not_synthetic_by_default(self, db):
        msg_id = write_message(
            db,
            session_id="s1",
            agent_id="a1",
            role="user",
            content="Real message",
        )
        row = db.execute(
            "SELECT synthetic FROM messages WHERE message_id = ?", [msg_id]
        ).fetchone()
        assert row[0] is False

    def test_sequence_auto_increment(self, db):
        assert get_next_sequence(db, "a1") == 0
        write_message(db, session_id="s1", agent_id="a1", role="user", content="msg1")
        assert get_next_sequence(db, "a1") == 1
        write_message(db, session_id="s1", agent_id="a1", role="assistant", content="msg2")
        assert get_next_sequence(db, "a1") == 2

    def test_explicit_sequence(self, db):
        write_message(
            db, session_id="s1", agent_id="a1", role="user", content="msg1", sequence=5
        )
        row = db.execute(
            "SELECT sequence FROM messages WHERE agent_id = 'a1'"
        ).fetchone()
        assert row[0] == 5

    def test_content_hash_computed(self, db):
        msg_id = write_message(
            db, session_id="s1", agent_id="a1", role="user", content="Hello"
        )
        row = db.execute(
            "SELECT content_hash FROM messages WHERE message_id = ?", [msg_id]
        ).fetchone()
        assert row[0] is not None
        assert len(row[0]) == 64  # SHA-256 hex

    def test_metadata_stored(self, db):
        meta = {"tool_name": "Bash", "tool_use_id": "tu_123"}
        msg_id = write_message(
            db,
            session_id="s1",
            agent_id="a1",
            role="tool",
            content="Tool output",
            metadata=meta,
        )
        row = db.execute(
            "SELECT metadata FROM messages WHERE message_id = ?", [msg_id]
        ).fetchone()
        stored = json.loads(row[0])
        assert stored["tool_name"] == "Bash"


class TestMessageQueries:
    def test_get_agent_messages_ordered(self, db):
        write_message(db, session_id="s1", agent_id="a1", role="user", content="first")
        write_message(db, session_id="s1", agent_id="a1", role="tool", content="tool call")
        write_message(db, session_id="s1", agent_id="a1", role="assistant", content="response")

        msgs = get_agent_messages(db, "a1")
        assert len(msgs) == 3
        assert [m["role"] for m in msgs] == ["user", "tool", "assistant"]
        assert [m["sequence"] for m in msgs] == [0, 1, 2]

    def test_get_agent_messages_isolation(self, db):
        write_message(db, session_id="s1", agent_id="a1", role="user", content="a1 msg")
        write_message(db, session_id="s1", agent_id="a2", role="user", content="a2 msg")

        msgs = get_agent_messages(db, "a1")
        assert len(msgs) == 1
        assert msgs[0]["content"] == "a1 msg"

    def test_get_session_messages(self, db):
        write_message(db, session_id="s1", agent_id="a1", role="user", content="a1 msg")
        write_message(db, session_id="s1", agent_id="a2", role="user", content="a2 msg")
        write_message(db, session_id="s2", agent_id="a3", role="user", content="s2 msg")

        msgs = get_session_messages(db, "s1")
        assert len(msgs) == 2

    def test_synthetic_flag_in_results(self, db):
        write_message(
            db, session_id="s1", agent_id="a1", role="assistant",
            content="inferred", synthetic=True,
        )
        msgs = get_agent_messages(db, "a1")
        assert msgs[0]["synthetic"] is True


class TestToolSummary:
    def test_empty_summary(self, db):
        summary = get_agent_tool_summary(db, "a1")
        assert summary["total"] == 0
        assert summary["tools"] == []

    def test_tool_summary_counts(self, db):
        # Insert PostToolUse events directly
        for tool in ["Bash", "Bash", "Read"]:
            write_event(db, {
                "event": {"event_type": "PostToolUse", "tool_name": tool},
                "session": {"session_id": "s1", "agent_id": "a1"},
            })
        write_event(db, {
            "event": {"event_type": "PostToolUseFailure", "tool_name": "Bash"},
            "session": {"session_id": "s1", "agent_id": "a1"},
        })

        summary = get_agent_tool_summary(db, "a1")
        assert summary["total"] == 4
        assert summary["successes"] == 3
        assert summary["failures"] == 1
        assert set(summary["tools"]) == {"Bash", "Read"}


class TestToolRole:
    def test_tool_role_accepted(self, db):
        msg_id = write_message(
            db, session_id="s1", agent_id="a1", role="tool",
            content="Tool call: Bash\nInput: ls -la",
        )
        row = db.execute(
            "SELECT role FROM messages WHERE message_id = ?", [msg_id]
        ).fetchone()
        assert row[0] == "tool"
