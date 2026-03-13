"""Integration tests for message extraction in the collector (issue #8)."""
import json
import pytest

from collector.collector import (
    _truncate,
    _extract_field,
    _handle_pre_tool_message,
    _handle_post_tool_message,
    _handle_subagent_stop_message,
)
from collector.ledger import init_db, write_event, get_agent_messages


class TestTruncate:
    def test_short_string(self):
        assert _truncate("hello") == "hello"

    def test_exact_limit(self):
        s = "x" * 500
        assert _truncate(s) == s

    def test_over_limit(self):
        s = "x" * 600
        result = _truncate(s)
        assert len(result) == 503  # 500 + "..."
        assert result.endswith("...")

    def test_custom_limit(self):
        assert _truncate("hello world", max_len=5) == "hello..."


class TestExtractField:
    def test_nested(self):
        payload = {"event": {"tool_name": "Bash"}}
        assert _extract_field(payload, "event.tool_name", "tool_name") == "Bash"

    def test_flat_fallback(self):
        payload = {"tool_name": "Read"}
        assert _extract_field(payload, "event.tool_name", "tool_name") == "Read"

    def test_nested_preferred(self):
        payload = {"event": {"tool_name": "Bash"}, "tool_name": "Read"}
        assert _extract_field(payload, "event.tool_name", "tool_name") == "Bash"

    def test_missing(self):
        assert _extract_field({}, "event.tool_name", "tool_name") is None


class TestPreToolMessage:
    @pytest.fixture
    def db(self):
        import collector.collector as c
        old_db = c._db
        c._db = init_db(":memory:")
        c._graph_conn = None
        yield c._db
        c._db = old_db

    def test_pre_tool_creates_message(self, db):
        payload = {
            "event": {
                "event_type": "PreToolUse",
                "tool_name": "Bash",
                "tool_use_id": "tu_1",
                "tool_input": {"command": "ls -la"},
            },
            "session": {"session_id": "s1", "agent_id": "a1"},
        }
        _handle_pre_tool_message("ev1", payload)

        msgs = get_agent_messages(db, "a1")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "tool"
        assert "Tool call: Bash" in msgs[0]["content"]
        assert "ls -la" in msgs[0]["content"]


class TestPostToolMessage:
    @pytest.fixture
    def db(self):
        import collector.collector as c
        old_db = c._db
        c._db = init_db(":memory:")
        c._graph_conn = None
        yield c._db
        c._db = old_db

    def test_post_tool_creates_message(self, db):
        payload = {
            "event": {
                "event_type": "PostToolUse",
                "tool_name": "Bash",
                "tool_use_id": "tu_1",
                "duration_ms": 42,
                "tool_response": "file1.txt\nfile2.txt",
            },
            "session": {"session_id": "s1", "agent_id": "a1"},
        }
        _handle_post_tool_message("ev1", payload)

        msgs = get_agent_messages(db, "a1")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "tool"
        assert "Tool result: Bash" in msgs[0]["content"]
        assert "success" in msgs[0]["content"]
        assert "42ms" in msgs[0]["content"]

    def test_failure_status(self, db):
        payload = {
            "event": {
                "event_type": "PostToolUseFailure",
                "tool_name": "Bash",
                "tool_use_id": "tu_2",
            },
            "session": {"session_id": "s1", "agent_id": "a1"},
        }
        _handle_post_tool_message("ev2", payload)

        msgs = get_agent_messages(db, "a1")
        assert "failed" in msgs[0]["content"]


class TestSubagentStopMessage:
    @pytest.fixture
    def db(self):
        import collector.collector as c
        old_db = c._db
        c._db = init_db(":memory:")
        c._graph_conn = None
        yield c._db
        c._db = old_db

    def test_synthetic_summary_no_tools(self, db):
        payload = {
            "event": {"event_type": "SubagentStop", "duration_ms": 1500},
            "session": {"session_id": "s1", "agent_id": "a1"},
        }
        _handle_subagent_stop_message("ev1", payload)

        msgs = get_agent_messages(db, "a1")
        assert len(msgs) == 1
        assert msgs[0]["synthetic"] is True
        assert msgs[0]["role"] == "assistant"
        assert "Agent completed" in msgs[0]["content"]
        assert "0 tool calls" in msgs[0]["content"]

    def test_synthetic_summary_with_tools(self, db):
        # Seed some tool events
        for tool in ["Bash", "Read", "Bash"]:
            write_event(db, {
                "event": {"event_type": "PostToolUse", "tool_name": tool},
                "session": {"session_id": "s1", "agent_id": "a1"},
            })

        payload = {
            "event": {"event_type": "SubagentStop", "duration_ms": 5000},
            "session": {"session_id": "s1", "agent_id": "a1"},
        }
        _handle_subagent_stop_message("ev1", payload)

        msgs = get_agent_messages(db, "a1")
        assert len(msgs) == 1
        assert "3 tool calls" in msgs[0]["content"]
        assert "Duration: 5000ms" in msgs[0]["content"]

    def test_real_response_when_result_present(self, db):
        payload = {
            "event": {
                "event_type": "SubagentStop",
                "result": "The agent produced this output.",
            },
            "session": {"session_id": "s1", "agent_id": "a1"},
        }
        _handle_subagent_stop_message("ev1", payload)

        msgs = get_agent_messages(db, "a1")
        assert len(msgs) == 1
        assert msgs[0]["synthetic"] is False
        assert msgs[0]["content"] == "The agent produced this output."

    def test_real_response_from_output_field(self, db):
        payload = {
            "event": {
                "event_type": "SubagentStop",
                "output": "Output via output field.",
            },
            "session": {"session_id": "s1", "agent_id": "a1"},
        }
        _handle_subagent_stop_message("ev1", payload)

        msgs = get_agent_messages(db, "a1")
        assert msgs[0]["synthetic"] is False
        assert msgs[0]["content"] == "Output via output field."
