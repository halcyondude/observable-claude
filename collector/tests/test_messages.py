import uuid

import duckdb
import pytest

from collector.ledger import init_db, write_message, get_agent_messages, search_messages


@pytest.fixture()
def conn(tmp_path):
    db_path = str(tmp_path / "test.db")
    return init_db(db_path)


def test_write_and_read_message(conn):
    mid = str(uuid.uuid4())
    write_message(conn, mid, "sess-1", "agent-1", "user", "hello world", 0)
    msgs = get_agent_messages(conn, "agent-1")
    assert len(msgs) == 1
    assert msgs[0]["message_id"] == mid
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "hello world"
    assert msgs[0]["sequence"] == 0
    assert msgs[0]["content_bytes"] == len("hello world".encode("utf-8"))


def test_messages_ordered_by_sequence(conn):
    for seq in [2, 0, 1]:
        write_message(conn, str(uuid.uuid4()), "sess-1", "agent-1", "user", f"msg-{seq}", seq)
    msgs = get_agent_messages(conn, "agent-1")
    assert [m["sequence"] for m in msgs] == [0, 1, 2]


def test_get_agent_messages_filters_by_agent(conn):
    write_message(conn, str(uuid.uuid4()), "sess-1", "agent-1", "user", "a1 msg", 0)
    write_message(conn, str(uuid.uuid4()), "sess-1", "agent-2", "user", "a2 msg", 0)
    msgs = get_agent_messages(conn, "agent-1")
    assert len(msgs) == 1
    assert msgs[0]["agent_id"] == "agent-1"


def test_search_messages_basic(conn):
    write_message(conn, str(uuid.uuid4()), "sess-1", "agent-1", "user", "implement the foobar feature", 0)
    write_message(conn, str(uuid.uuid4()), "sess-1", "agent-1", "assistant", "done with baz", 1)
    results = search_messages(conn, "foobar")
    assert len(results) == 1
    assert results[0]["role"] == "user"


def test_search_messages_case_insensitive(conn):
    write_message(conn, str(uuid.uuid4()), "sess-1", "agent-1", "user", "Check the ERROR logs", 0)
    results = search_messages(conn, "error")
    assert len(results) == 1


def test_search_messages_filter_by_session(conn):
    write_message(conn, str(uuid.uuid4()), "sess-1", "agent-1", "user", "find the bug", 0)
    write_message(conn, str(uuid.uuid4()), "sess-2", "agent-2", "user", "find the bug", 0)
    results = search_messages(conn, "bug", session_id="sess-1")
    assert len(results) == 1
    assert results[0]["session_id"] == "sess-1"


def test_search_returns_content_preview(conn):
    long_content = "x" * 1000
    write_message(conn, str(uuid.uuid4()), "sess-1", "agent-1", "user", long_content, 0)
    results = search_messages(conn, "xxx")
    assert len(results) == 1
    assert len(results[0]["content_preview"]) == 500


def test_write_message_empty_content(conn):
    mid = str(uuid.uuid4())
    write_message(conn, mid, "sess-1", "agent-1", "user", "", 0)
    msgs = get_agent_messages(conn, "agent-1")
    assert len(msgs) == 1
    assert msgs[0]["content_bytes"] == 0
