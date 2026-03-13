"""Tests for message search and query integration (#7)."""

import os
import tempfile

import duckdb
import pytest

from collector.ledger import init_db, write_message, search_messages, get_session_messages, _build_snippet


@pytest.fixture
def db():
    """Create a temporary DuckDB database with schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.db")
        conn = init_db(path)
        yield conn
        conn.close()


@pytest.fixture
def db_with_messages(db):
    """Seed the database with test messages."""
    messages = [
        {"session_id": "s1", "agent_id": "a1", "role": "user", "sequence": 0,
         "content": "Please deploy the application to staging"},
        {"session_id": "s1", "agent_id": "a1", "role": "assistant", "sequence": 1,
         "content": "I'll deploy the application now. Running deploy script..."},
        {"session_id": "s1", "agent_id": "a1", "role": "user", "sequence": 2,
         "content": "Check the test results after deployment"},
        {"session_id": "s1", "agent_id": "a2", "role": "user", "sequence": 0,
         "content": "Run the integration tests for the API module"},
        {"session_id": "s1", "agent_id": "a2", "role": "assistant", "sequence": 1,
         "content": "Tests completed. 3 failures found in error handling."},
        {"session_id": "s2", "agent_id": "a3", "role": "system", "sequence": 0,
         "content": "You are a code review agent. Check for errors and security issues."},
    ]
    for msg in messages:
        write_message(db, event_id=None, **msg)
    return db


class TestWriteMessage:
    def test_write_returns_message_id(self, db):
        mid = write_message(
            db, event_id=None, session_id="s1", agent_id="a1",
            role="user", sequence=0, content="hello world"
        )
        assert mid is not None
        assert len(mid) == 36  # UUID format

    def test_message_stored_correctly(self, db):
        write_message(
            db, event_id="evt1", session_id="s1", agent_id="a1",
            role="assistant", sequence=1, content="response text"
        )
        rows = db.execute("SELECT * FROM messages").fetchall()
        assert len(rows) == 1

    def test_content_hash_computed(self, db):
        write_message(
            db, event_id=None, session_id="s1", agent_id="a1",
            role="user", sequence=0, content="test content"
        )
        row = db.execute("SELECT content_hash, content_bytes FROM messages").fetchone()
        assert row[0] is not None  # hash present
        assert row[1] == len("test content".encode())

    def test_null_content_handled(self, db):
        mid = write_message(
            db, event_id=None, session_id="s1", agent_id="a1",
            role="user", sequence=0, content=None
        )
        assert mid is not None
        row = db.execute("SELECT content_hash, content_bytes FROM messages").fetchone()
        assert row[0] is None
        assert row[1] == 0


class TestBuildSnippet:
    def test_basic_match(self):
        result = _build_snippet("hello world this is a test string", "test")
        assert result is not None
        assert "**test**" in result

    def test_match_with_context(self):
        content = "a" * 100 + "MATCH" + "b" * 100
        result = _build_snippet(content, "MATCH", context_chars=10)
        assert result is not None
        assert "**MATCH**" in result
        assert result.startswith("...")
        assert result.endswith("...")

    def test_no_match(self):
        result = _build_snippet("hello world", "xyz")
        assert result is None

    def test_empty_content(self):
        result = _build_snippet("", "test")
        assert result is None

    def test_regex_match(self):
        result = _build_snippet("error 404 not found", "error|fail")
        assert result is not None
        assert "**error**" in result

    def test_invalid_regex_falls_back_to_literal(self):
        result = _build_snippet("test [bracket text", "[bracket")
        assert result is not None
        assert "**[bracket**" in result


class TestSearchMessages:
    def test_basic_search(self, db_with_messages):
        results = search_messages(db_with_messages, q="deploy")
        assert len(results) == 3  # "deploy" matches deploy, deploy, deployment
        for r in results:
            assert "snippet" in r
            assert "content_preview" in r
            assert "content" not in r  # full content stripped

    def test_search_by_role(self, db_with_messages):
        results = search_messages(db_with_messages, q="test", role="user")
        assert all(r["role"] == "user" for r in results)

    def test_search_by_agent_id(self, db_with_messages):
        results = search_messages(db_with_messages, q="test", agent_id="a2")
        assert all(r["agent_id"] == "a2" for r in results)

    def test_search_by_session_id(self, db_with_messages):
        results = search_messages(db_with_messages, q="error", session_id="s2")
        assert len(results) == 1
        assert results[0]["session_id"] == "s2"

    def test_search_no_results(self, db_with_messages):
        results = search_messages(db_with_messages, q="nonexistent_term_xyz")
        assert results == []

    def test_search_pagination(self, db_with_messages):
        all_results = search_messages(db_with_messages, q=".*", limit=100)
        page1 = search_messages(db_with_messages, q=".*", limit=2, offset=0)
        page2 = search_messages(db_with_messages, q=".*", limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0]["message_id"] != page2[0]["message_id"]

    def test_search_results_have_snippet(self, db_with_messages):
        results = search_messages(db_with_messages, q="deploy")
        for r in results:
            assert r["snippet"] is not None
            assert "**" in r["snippet"]

    def test_regex_search(self, db_with_messages):
        results = search_messages(db_with_messages, q="error|fail")
        assert len(results) >= 2  # "error handling" and "errors and security"


class TestGetSessionMessages:
    def test_get_session_messages(self, db_with_messages):
        results = get_session_messages(db_with_messages, "s1")
        assert len(results) == 5
        assert all(r["session_id"] == "s1" for r in results)

    def test_messages_ordered_by_timestamp(self, db_with_messages):
        results = get_session_messages(db_with_messages, "s1")
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps)

    def test_different_session(self, db_with_messages):
        results = get_session_messages(db_with_messages, "s2")
        assert len(results) == 1
        assert results[0]["role"] == "system"

    def test_empty_session(self, db_with_messages):
        results = get_session_messages(db_with_messages, "nonexistent")
        assert results == []

    def test_content_preview_included(self, db_with_messages):
        results = get_session_messages(db_with_messages, "s1")
        for r in results:
            assert "content_preview" in r
            assert "content" not in r  # full content stripped
