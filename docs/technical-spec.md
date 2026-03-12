---
title: Technical Specification
description: Graph schema, DuckDB schema, API reference, hook events, NL-to-Cypher pipeline, and module structure
---

# Technical Specification

## Graph Schema (LadybugDB)

The execution graph is a labeled property graph stored in LadybugDB (a Kuzu fork). Four node types and three relationship types capture the full topology of a Claude Code session.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#0A9396'}}}%%
erDiagram
    Session ||--o{ Agent : "SPAWNED"
    Agent ||--o{ Agent : "SPAWNED"
    Agent }o--o{ Tool : "INVOKED"
    Agent }o--o{ Skill : "LOADED"

    Session {
        STRING session_id PK "Unique session identifier"
        STRING cwd "Working directory"
        STRING start_ts "ISO 8601 start time"
        STRING end_ts "ISO 8601 end time (null if active)"
    }

    Agent {
        STRING agent_id PK "Unique agent identifier"
        STRING agent_type "e.g. planner, implementer, reviewer"
        STRING session_id "FK to parent session"
        STRING start_ts "ISO 8601 start time"
        STRING end_ts "ISO 8601 end time (null if running)"
        STRING status "running | complete | failed"
    }

    Tool {
        STRING name PK "e.g. Bash, Write, Read, mcp__*"
    }

    Skill {
        STRING name PK "e.g. observer-context"
        STRING path "Filesystem path to SKILL.md"
    }
```

### Node DDL

```sql
CREATE NODE TABLE Session (
    session_id STRING, cwd STRING,
    start_ts STRING, end_ts STRING,
    PRIMARY KEY (session_id)
);

CREATE NODE TABLE Agent (
    agent_id STRING, agent_type STRING, session_id STRING,
    start_ts STRING, end_ts STRING, status STRING,
    PRIMARY KEY (agent_id)
);

CREATE NODE TABLE Skill (name STRING, path STRING, PRIMARY KEY (name));
CREATE NODE TABLE Tool  (name STRING, PRIMARY KEY (name));
```

### Relationship DDL

```sql
CREATE REL TABLE SPAWNED (
    FROM Session TO Agent, FROM Agent TO Agent,
    prompt STRING, depth INT64, spawned_at STRING
);

CREATE REL TABLE LOADED (
    FROM Agent TO Skill,
    loaded_at STRING
);

CREATE REL TABLE INVOKED (
    FROM Agent TO Tool,
    tool_use_id STRING, tool_input STRING,
    start_ts STRING, end_ts STRING,
    duration_ms INT64, status STRING, tool_response STRING
);
```

### Relationship Properties

| Relationship | Property | Type | Description |
|---|---|---|---|
| `SPAWNED` | `prompt` | STRING | Prompt text that triggered the spawn |
| `SPAWNED` | `depth` | INT64 | Depth in the spawn tree (0 = session root) |
| `SPAWNED` | `spawned_at` | STRING | ISO 8601 timestamp |
| `LOADED` | `loaded_at` | STRING | ISO 8601 timestamp |
| `INVOKED` | `tool_use_id` | STRING | Correlation key linking Pre/PostToolUse |
| `INVOKED` | `tool_input` | STRING | JSON-serialized tool input |
| `INVOKED` | `start_ts` | STRING | When PreToolUse fired |
| `INVOKED` | `end_ts` | STRING | When PostToolUse/Failure fired |
| `INVOKED` | `duration_ms` | INT64 | End-to-end tool call duration |
| `INVOKED` | `status` | STRING | `pending` / `success` / `failed` |
| `INVOKED` | `tool_response` | STRING | Truncated response (max 2000 chars) |

### Design Decisions

**Why Skill is a node, not an edge property:** Cross-session queries like "which agents loaded the observer-context skill?" require traversal to a shared entity. Edge properties can't be traversed to. Nodes win for anything you want to query across sessions.

**Why prompt is an edge property, not a Prompt node:** Prompts are metadata on spawn transitions, not entities you traverse to independently. DuckDB handles full-text search on prompts via the raw payload JSON column.

## DuckDB Schema

DuckDB stores every hook event as a flat row. It is the immutable source of truth — if LadybugDB gets corrupted, `scripts/replay.py` rebuilds the graph from DuckDB events.

```sql
CREATE TABLE events (
    event_id    VARCHAR PRIMARY KEY,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type  VARCHAR NOT NULL,
    session_id  VARCHAR,
    agent_id    VARCHAR,
    agent_type  VARCHAR,
    tool_use_id VARCHAR,
    tool_name   VARCHAR,
    cwd         VARCHAR,
    payload     JSON
);

-- Indexes for common query patterns
CREATE INDEX idx_session   ON events(session_id);
CREATE INDEX idx_tool_pair ON events(tool_use_id);  -- correlate Pre/PostToolUse
CREATE INDEX idx_type      ON events(event_type);
CREATE INDEX idx_time      ON events(received_at);
```

### Field Extraction

The collector extracts structured fields from the hook payload before writing to DuckDB. Claude Code hook payloads use a nested structure:

```json
{
  "event": {
    "event_type": "PreToolUse",
    "tool_name": "Bash",
    "tool_use_id": "toolu_abc123",
    "tool_input": {"command": "ls -la"}
  },
  "session": {
    "session_id": "sess_xyz",
    "agent_id": "agent_001",
    "agent_type": "implementer",
    "cwd": "/home/user/project"
  }
}
```

The `ledger.py` module extracts from the nested structure with a flat fallback for forward compatibility.

## Collector API Reference

All endpoints are served by a single FastAPI application on internal port 8000. Docker Compose maps this to external ports 4001 (ingestion) and 4002 (API).

### Event Ingestion

#### `POST /events`

Hook ingestion endpoint. Accepts a Claude Code hook payload, writes to DuckDB, materializes in LadybugDB, and broadcasts via SSE.

**Request:**
```json
{
  "event": {"event_type": "SessionStart", "timestamp": "2025-01-15T10:30:00Z"},
  "session": {"session_id": "sess_abc", "cwd": "/home/user/project"}
}
```

**Response:**
```json
{"event_id": "550e8400-e29b-41d4-a716-446655440000", "status": "ok"}
```

Graph materialization is best-effort — if it fails, the event is still persisted in DuckDB and broadcast via SSE. Errors are logged but never block ingestion.

### Health

#### `GET /health`

Liveness check with basic stats.

**Response:**
```json
{"status": "ok", "events_total": 1247, "uptime_seconds": 3600.5}
```

### SSE Stream

#### `GET /stream`

Server-Sent Events stream. Each ingested event is pushed to all connected clients as an SSE frame.

**SSE frame format:**
```
event: PreToolUse
data: {"event_id": "...", "event": {"event_type": "PreToolUse", ...}, "session": {...}}
```

The `event:` field is set to the `event_type`, enabling client-side filtering. Uses `asyncio.Queue` per client with a 256-event buffer — slow clients get dropped.

### Session Endpoints

#### `GET /api/sessions`

All sessions, ordered by first event time descending.

**Response:**
```json
[
  {"session_id": "sess_abc", "first_event": "2025-01-15T10:30:00Z", "last_event": "2025-01-15T11:45:00Z", "cwd": "/home/user/project"}
]
```

#### `GET /api/sessions/active`

Sessions with a `SessionStart` event but no `SessionEnd`.

#### `GET /api/sessions/{id}/graph`

Cytoscape.js-compatible JSON for the session's execution graph.

**Response:**
```json
{
  "nodes": [
    {"data": {"id": "sess_abc", "label": "Session", "type": "Session", "cwd": "/home/user/project"}},
    {"data": {"id": "agent_001", "label": "planner", "type": "Agent", "status": "running"}}
  ],
  "edges": [
    {"data": {"source": "sess_abc", "target": "agent_001", "label": "SPAWNED", "prompt": "Plan the implementation"}}
  ]
}
```

#### `GET /api/sessions/{id}/timeline`

Gantt-compatible timeline data with nested tool events.

**Response:**
```json
[
  {
    "agent_id": "agent_001",
    "agent_type": "planner",
    "start_ts": "2025-01-15T10:30:05Z",
    "end_ts": "2025-01-15T10:32:15Z",
    "status": "complete",
    "depth": 0,
    "tool_events": [
      {"tool_use_id": "toolu_1", "tool_name": "Read", "start_ts": "...", "end_ts": "...", "status": "success"}
    ]
  }
]
```

### Event Query

#### `GET /api/events`

Paginated raw events from DuckDB.

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `event_type` | string | — | Filter by event type |
| `session_id` | string | — | Filter by session |
| `agent_id` | string | — | Filter by agent |
| `tool_use_id` | string | — | Filter by tool call |
| `limit` | int | 100 | Results per page (1–1000) |
| `offset` | int | 0 | Pagination offset |

### NL and Cypher Query

#### `POST /api/ask`

Translate a natural language question to Cypher, execute it, and return results.

**Request:**
```json
{"question": "which agents are currently running?"}
```

**Response (success):**
```json
{
  "cypher": "MATCH (a:Agent {status: 'running'}) RETURN a.agent_id, a.agent_type, a.start_ts ORDER BY a.start_ts",
  "explanation": "Finds all agents with status 'running', ordered by start time",
  "result": [
    {"a.agent_id": "agent_001", "a.agent_type": "planner", "a.start_ts": "2025-01-15T10:30:05Z"}
  ]
}
```

**Response (error):**
```json
{"error": "Query failed", "details": "..."}
```

#### `POST /api/cypher`

Execute raw Cypher directly against LadybugDB.

**Request:**
```json
{"cypher": "MATCH (s:Session) RETURN s.session_id, s.cwd"}
```

**Response:**
```json
{
  "result": [{"s.session_id": "sess_abc", "s.cwd": "/home/user/project"}]
}
```

### Graph Management

#### `POST /api/replay`

Rebuild the LadybugDB graph from all DuckDB events. Drops all graph tables, recreates them, and replays every event in chronological order.

**Response:**
```json
{"status": "ok", "events_replayed": 1247, "errors": 0}
```

## Hook Event Reference

Claude Code fires 12 lifecycle event types. CC Observer handles each differently.

| Event | Group | Graph Mutation | DuckDB | SSE |
|---|---|---|---|---|
| `SessionStart` | Session | CREATE/MERGE Session node | Yes | Yes |
| `SessionEnd` | Session | SET Session.end_ts | Yes | Yes |
| `SubagentStart` | Agent | CREATE Agent + SPAWNED edge | Yes | Yes |
| `SubagentStop` | Agent | SET Agent.end_ts, status | Yes | Yes |
| `Stop` | Agent | SET Agent.status=complete | Yes | Yes |
| `UserPromptSubmit` | Conversation | No-op (stored in DuckDB only) | Yes | Yes |
| `PreToolUse` | Tool | MERGE Tool + CREATE INVOKED (pending) | Yes | Yes |
| `PostToolUse` | Tool | SET INVOKED status=success, duration_ms | Yes | Yes |
| `PostToolUseFailure` | Tool | SET INVOKED status=failed | Yes | Yes |
| `Notification` | Conversation | No-op | Yes | Yes |
| `PermissionRequest` | Tool | No-op | Yes | Yes |
| `PreCompact` | Maintenance | No-op (future: graph snapshot) | Yes | Yes |

**Correlation keys:**

- `session_id` — groups all events in a session
- `agent_id` — identifies which agent generated the event
- `tool_use_id` — links `PreToolUse` to its `PostToolUse` or `PostToolUseFailure` for span timing

**Hook delivery modes:**

- `SessionStart` through `PostToolUseFailure` (9 events): HTTP primary + command fallback
- `PermissionRequest`, `Notification`, `PreCompact` (3 events): HTTP only (no command fallback — subprocess spawn during permission dialogs would block Claude Code)

## NL-to-Cypher Pipeline

Natural language questions are translated to Cypher queries using the Anthropic API, then executed against LadybugDB.

```mermaid
%%{init: {'theme': 'dark'}}%%
sequenceDiagram
    participant USER as User / Dashboard
    participant API as POST /api/ask
    participant NL as nl_query.py
    participant ANTH as Anthropic API
    participant KUZU as LadybugDB

    USER->>API: {"question": "which agents are running?"}
    API->>NL: translate(question, client)

    NL->>ANTH: messages.create()
    Note right of NL: model: claude-sonnet-4-6<br/>system: schema + rules + examples<br/>user: question

    ANTH-->>NL: {"cypher": "MATCH ...", "explanation": "..."}
    NL-->>API: {cypher, explanation}

    API->>KUZU: conn.execute(cypher)
    KUZU-->>API: result rows

    API-->>USER: {cypher, explanation, result}
```

### System Prompt Structure

The NL-to-Cypher system prompt includes:

1. **Full graph DDL** — all CREATE statements for nodes and relationships
2. **Property types and enums** — status values (`running`, `complete`, `failed`, `pending`, `success`)
3. **Rules** — read-only queries only, timestamp format, aggregation functions
4. **Six example question-to-Cypher pairs** covering common query patterns
5. **Output format** — strict JSON: `{"cypher": "...", "explanation": "..."}`

### Example Translations

| Natural Language | Generated Cypher |
|---|---|
| Which agents are currently running? | `MATCH (a:Agent {status: 'running'}) RETURN a.agent_id, a.agent_type, a.start_ts ORDER BY a.start_ts` |
| Show me the spawn tree | `MATCH (s:Session)-[r:SPAWNED*]->(a:Agent) RETURN s.session_id, a.agent_id, a.agent_type, a.status` |
| What tool calls failed? | `MATCH (a:Agent)-[r:INVOKED {status: 'failed'}]->(t:Tool) RETURN a.agent_id, t.name, r.tool_input, r.start_ts` |
| What was the slowest tool call? | `MATCH (a:Agent)-[r:INVOKED]->(t:Tool) WHERE r.duration_ms IS NOT NULL RETURN t.name, r.duration_ms, a.agent_id ORDER BY r.duration_ms DESC LIMIT 1` |
| What skills were loaded? | `MATCH (a:Agent)-[:LOADED]->(s:Skill) RETURN DISTINCT s.name` |

## SSE Protocol

The SSE stream uses standard `text/event-stream` format with typed events for client-side filtering.

**Connection:** `GET /stream` returns `Content-Type: text/event-stream`

**Frame format:**
```
event: PreToolUse
data: {"event_id":"550e8400-...","event":{"event_type":"PreToolUse","tool_name":"Bash"},"session":{"session_id":"sess_abc"}}

```

**Client behavior:**
- Each client gets a dedicated `asyncio.Queue` (max 256 events)
- If a client falls behind (queue full), it is disconnected and must reconnect
- On reconnect, the client should re-fetch the current session graph via `GET /api/sessions/{id}/graph` to fill any missed events

## Python Module Structure

```mermaid
%%{init: {'theme': 'dark'}}%%
classDiagram
    class collector {
        +app: FastAPI
        +ingest_event(request) dict
        +health() dict
        +stream() EventSourceResponse
        +list_sessions() list
        +list_active_sessions() list
        +list_events(...) list
        +session_graph(session_id) dict
        +session_timeline(session_id) list
        +ask(request) dict
        +execute_cypher(request) dict
        +replay() dict
    }

    class ledger {
        +init_db(path) DuckDBPyConnection
        +write_event(conn, event) str
        +query_events(conn, filters, limit, offset) list
        +get_sessions(conn) list
        +get_active_sessions(conn) list
    }

    class graph {
        +init_graph(db_path) tuple
        +reset_graph(conn) None
        +materialize_event(conn, event) None
        +get_session_graph(conn, session_id) dict
        +get_session_timeline(conn, session_id) list
    }

    class nl_query {
        +SYSTEM_PROMPT: str
        +translate(question, client) dict
    }

    collector --> ledger : write_event, query
    collector --> graph : materialize, query
    collector --> nl_query : translate

    note for collector "FastAPI app\nEvent ingestion + API + SSE"
    note for ledger "DuckDB operations\nImmutable event ledger"
    note for graph "LadybugDB operations\nCypher mutations + queries"
    note for nl_query "Anthropic API\nNL to Cypher translation"
```
