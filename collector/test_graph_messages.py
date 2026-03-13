"""Tests for Message graph schema and materialization in graph.py."""

import tempfile
import os

import pytest

from collector.graph import (
    init_graph,
    reset_graph,
    materialize_event,
    materialize_message,
    get_session_graph,
    get_agent_messages_graph,
    CONTENT_PREVIEW_LIMIT,
)


@pytest.fixture
def graph_conn(tmp_path):
    """Create a fresh LadybugDB graph and return (db, conn)."""
    db_path = str(tmp_path / "test_ladybug.db")
    db, conn = init_graph(db_path)
    yield conn


def _make_subagent_start(agent_id, session_id, prompt="do stuff", parent_agent_id=None, ts="2025-01-01T00:00:00Z"):
    event = {
        "event": {
            "event_type": "SubagentStart",
            "prompt": prompt,
            "depth": 1,
            "timestamp": ts,
        },
        "session": {
            "agent_id": agent_id,
            "agent_type": "specialist",
            "session_id": session_id,
        },
    }
    if parent_agent_id:
        event["event"]["parent_agent_id"] = parent_agent_id
    return event


class TestDDL:
    """Message, HAS_MESSAGE, and NEXT tables are created by init_graph."""

    def test_message_node_table_exists(self, graph_conn):
        # If the table doesn't exist, this query will raise
        result = graph_conn.execute("MATCH (m:Message) RETURN m.message_id")
        assert result.get_all() == []

    def test_has_message_rel_exists(self, graph_conn):
        # Create prerequisite nodes
        graph_conn.execute("CREATE (a:Agent {agent_id: 'a1', agent_type: 'test', session_id: 's1', start_ts: '', end_ts: '', status: 'running'})")
        graph_conn.execute("CREATE (m:Message {message_id: 'm1', role: 'user', content_preview: 'hi', sequence: 0, timestamp: '', content_bytes: 2})")
        graph_conn.execute(
            "MATCH (a:Agent {agent_id: 'a1'}), (m:Message {message_id: 'm1'}) "
            "CREATE (a)-[:HAS_MESSAGE]->(m)"
        )
        result = graph_conn.execute(
            "MATCH (a:Agent)-[:HAS_MESSAGE]->(m:Message) RETURN a.agent_id, m.message_id"
        )
        rows = result.get_all()
        assert len(rows) == 1
        assert rows[0] == ["a1", "m1"]

    def test_next_rel_exists(self, graph_conn):
        graph_conn.execute("CREATE (m1:Message {message_id: 'm1', role: 'user', content_preview: '', sequence: 0, timestamp: '', content_bytes: 0})")
        graph_conn.execute("CREATE (m2:Message {message_id: 'm2', role: 'assistant', content_preview: '', sequence: 1, timestamp: '', content_bytes: 0})")
        graph_conn.execute(
            "MATCH (m1:Message {message_id: 'm1'}), (m2:Message {message_id: 'm2'}) "
            "CREATE (m1)-[:NEXT]->(m2)"
        )
        result = graph_conn.execute(
            "MATCH (m1:Message)-[:NEXT]->(m2:Message) RETURN m1.message_id, m2.message_id"
        )
        rows = result.get_all()
        assert len(rows) == 1
        assert rows[0] == ["m1", "m2"]


class TestResetGraph:
    """reset_graph drops and recreates all tables including new ones."""

    def test_reset_clears_messages(self, graph_conn):
        graph_conn.execute("CREATE (m:Message {message_id: 'm1', role: 'user', content_preview: '', sequence: 0, timestamp: '', content_bytes: 0})")
        reset_graph(graph_conn)
        result = graph_conn.execute("MATCH (m:Message) RETURN m.message_id")
        assert result.get_all() == []


class TestDropStatementOrder:
    """DROP_STATEMENTS must drop rel tables before node tables."""

    def test_drop_order(self):
        from collector.graph import DROP_STATEMENTS
        # NEXT and HAS_MESSAGE depend on Message, must come before Message drop
        next_idx = next(i for i, s in enumerate(DROP_STATEMENTS) if "NEXT" in s)
        has_msg_idx = next(i for i, s in enumerate(DROP_STATEMENTS) if "HAS_MESSAGE" in s)
        msg_idx = next(i for i, s in enumerate(DROP_STATEMENTS) if "Message" in s and "HAS_MESSAGE" not in s)
        assert next_idx < msg_idx
        assert has_msg_idx < msg_idx


class TestMaterializeMessage:
    """materialize_message creates nodes, HAS_MESSAGE, and NEXT edges."""

    def test_creates_message_node(self, graph_conn):
        graph_conn.execute("CREATE (a:Agent {agent_id: 'a1', agent_type: 'test', session_id: 's1', start_ts: '', end_ts: '', status: 'running'})")
        materialize_message(graph_conn, "a1", "m1", "user", "hello world", 0, "2025-01-01T00:00:00Z")

        result = graph_conn.execute("MATCH (m:Message {message_id: 'm1'}) RETURN m.role, m.content_preview, m.sequence, m.content_bytes")
        rows = result.get_all()
        assert len(rows) == 1
        assert rows[0][0] == "user"
        assert rows[0][1] == "hello world"
        assert rows[0][2] == 0
        assert rows[0][3] == 11  # len("hello world".encode())

    def test_creates_has_message_edge(self, graph_conn):
        graph_conn.execute("CREATE (a:Agent {agent_id: 'a1', agent_type: 'test', session_id: 's1', start_ts: '', end_ts: '', status: 'running'})")
        materialize_message(graph_conn, "a1", "m1", "user", "hi", 0, "2025-01-01T00:00:00Z")

        result = graph_conn.execute("MATCH (a:Agent {agent_id: 'a1'})-[:HAS_MESSAGE]->(m:Message) RETURN m.message_id")
        assert result.get_all() == [["m1"]]

    def test_creates_next_edge_for_sequence_gt_0(self, graph_conn):
        graph_conn.execute("CREATE (a:Agent {agent_id: 'a1', agent_type: 'test', session_id: 's1', start_ts: '', end_ts: '', status: 'running'})")
        materialize_message(graph_conn, "a1", "m0", "user", "first", 0, "2025-01-01T00:00:00Z")
        materialize_message(graph_conn, "a1", "m1", "assistant", "second", 1, "2025-01-01T00:00:01Z")

        result = graph_conn.execute("MATCH (m1:Message)-[:NEXT]->(m2:Message) RETURN m1.message_id, m2.message_id")
        rows = result.get_all()
        assert len(rows) == 1
        assert rows[0] == ["m0", "m1"]

    def test_no_next_edge_for_sequence_0(self, graph_conn):
        graph_conn.execute("CREATE (a:Agent {agent_id: 'a1', agent_type: 'test', session_id: 's1', start_ts: '', end_ts: '', status: 'running'})")
        materialize_message(graph_conn, "a1", "m0", "user", "first", 0, "2025-01-01T00:00:00Z")

        result = graph_conn.execute("MATCH ()-[:NEXT]->() RETURN count(*)")
        assert result.get_all()[0][0] == 0

    def test_content_preview_truncated(self, graph_conn):
        graph_conn.execute("CREATE (a:Agent {agent_id: 'a1', agent_type: 'test', session_id: 's1', start_ts: '', end_ts: '', status: 'running'})")
        long_content = "x" * 1000
        materialize_message(graph_conn, "a1", "m1", "user", long_content, 0, "2025-01-01T00:00:00Z")

        result = graph_conn.execute("MATCH (m:Message {message_id: 'm1'}) RETURN m.content_preview, m.content_bytes")
        rows = result.get_all()
        assert len(rows[0][0]) == CONTENT_PREVIEW_LIMIT
        assert rows[0][1] == 1000

    def test_idempotent_merge(self, graph_conn):
        graph_conn.execute("CREATE (a:Agent {agent_id: 'a1', agent_type: 'test', session_id: 's1', start_ts: '', end_ts: '', status: 'running'})")
        materialize_message(graph_conn, "a1", "m1", "user", "hi", 0, "2025-01-01T00:00:00Z")
        materialize_message(graph_conn, "a1", "m1", "user", "hi", 0, "2025-01-01T00:00:00Z")

        result = graph_conn.execute("MATCH (m:Message {message_id: 'm1'}) RETURN count(*)")
        assert result.get_all()[0][0] == 1


class TestSubagentStartMessage:
    """SubagentStart event creates a Message node from the prompt."""

    def test_subagent_start_creates_message(self, graph_conn):
        event = _make_subagent_start("agent-1", "sess-1", prompt="Build the thing")
        materialize_event(graph_conn, event)

        result = graph_conn.execute("MATCH (m:Message) RETURN m.message_id, m.role, m.content_preview, m.sequence")
        rows = result.get_all()
        assert len(rows) == 1
        assert rows[0][0] == "msg-agent-1-0"
        assert rows[0][1] == "user"
        assert rows[0][2] == "Build the thing"
        assert rows[0][3] == 0

    def test_subagent_start_creates_has_message_edge(self, graph_conn):
        event = _make_subagent_start("agent-1", "sess-1", prompt="Build the thing")
        materialize_event(graph_conn, event)

        result = graph_conn.execute(
            "MATCH (a:Agent {agent_id: 'agent-1'})-[:HAS_MESSAGE]->(m:Message) RETURN m.message_id"
        )
        assert result.get_all() == [["msg-agent-1-0"]]

    def test_subagent_start_no_message_without_prompt(self, graph_conn):
        event = _make_subagent_start("agent-1", "sess-1", prompt="")
        materialize_event(graph_conn, event)

        result = graph_conn.execute("MATCH (m:Message) RETURN count(*)")
        assert result.get_all()[0][0] == 0


class TestGetSessionGraph:
    """get_session_graph includes Message nodes and HAS_MESSAGE/NEXT edges."""

    def test_includes_messages_in_graph(self, graph_conn):
        event = _make_subagent_start("agent-1", "sess-1", prompt="hello")
        materialize_event(graph_conn, event)

        graph = get_session_graph(graph_conn, "sess-1")
        msg_nodes = [n for n in graph["nodes"] if n["data"]["type"] == "Message"]
        assert len(msg_nodes) == 1
        assert msg_nodes[0]["data"]["message_id"] == "msg-agent-1-0"
        assert msg_nodes[0]["data"]["role"] == "user"

        has_msg_edges = [e for e in graph["edges"] if e["data"]["label"] == "HAS_MESSAGE"]
        assert len(has_msg_edges) == 1
        assert has_msg_edges[0]["data"]["source"] == "agent-1"
        assert has_msg_edges[0]["data"]["target"] == "msg-agent-1-0"


class TestGetAgentMessagesGraph:
    """get_agent_messages_graph returns linked list subgraph."""

    def test_returns_messages_for_agent(self, graph_conn):
        graph_conn.execute("CREATE (a:Agent {agent_id: 'a1', agent_type: 'test', session_id: 's1', start_ts: '', end_ts: '', status: 'running'})")
        materialize_message(graph_conn, "a1", "m0", "user", "first", 0, "2025-01-01T00:00:00Z")
        materialize_message(graph_conn, "a1", "m1", "assistant", "second", 1, "2025-01-01T00:00:01Z")

        graph = get_agent_messages_graph(graph_conn, "a1")
        assert len(graph["nodes"]) == 2
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["data"]["source"] == "m0"
        assert graph["edges"][0]["data"]["target"] == "m1"

    def test_empty_for_unknown_agent(self, graph_conn):
        graph = get_agent_messages_graph(graph_conn, "nonexistent")
        assert graph == {"nodes": [], "edges": []}
