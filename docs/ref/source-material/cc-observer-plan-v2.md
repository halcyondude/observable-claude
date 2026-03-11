# CC Observer — Complete Architecture & Plugin Plan v2

> Real-time execution graph monitoring for Claude Code.
> DuckDB raw event ledger · LadybugDB labeled property graph · Dockerized collector · Claude Code plugin with skills, commands, hooks, and NL→Cypher query interface.

---

## 1. System Overview

Claude Code fires lifecycle events through hooks. CC Observer plugin captures every event via dual delivery (http primary, command fallback), writes raw payloads to DuckDB, and materializes a live labeled property graph in LadybugDB (Kùzu fork). A SvelteKit dashboard consumes SSE from the collector. The entire backend runs as a Docker Compose stack. The plugin manages it.

---

## 2. Hook Event Reference

| Event | Group | Observer Action |
|---|---|---|
| `Setup` | Session | ignore |
| `SessionStart` | Session | CREATE Session node |
| `SessionEnd` | Session | SET Session.end_ts |
| `UserPromptSubmit` | Conversation | edge property on SPAWNED |
| `Notification` | Conversation | DuckDB only |
| `Stop` | Conversation | SET Agent.status=complete |
| `PreToolUse` | Tool | open INVOKED edge |
| `PermissionRequest` | Tool | DuckDB only |
| `PostToolUse` | Tool | close INVOKED edge + duration_ms |
| `PostToolUseFailure` | Tool | SET INVOKED.status=failed |
| `SubagentStart` | Subagent | CREATE Agent node + SPAWNED edge |
| `SubagentStop` | Subagent | SET Agent.end_ts + status |
| `PreCompact` | Maintenance | graph snapshot to DuckDB |

Correlation keys: `session_id` + `agent_id` + `tool_use_id`

---

## 3. Graph Data Model (LadybugDB / Kùzu)

```cypher
-- Nodes
CREATE NODE TABLE Session (session_id STRING, cwd STRING, start_ts TIMESTAMP, end_ts TIMESTAMP, PRIMARY KEY (session_id));
CREATE NODE TABLE Agent (agent_id STRING, agent_type STRING, session_id STRING, start_ts TIMESTAMP, end_ts TIMESTAMP, status STRING, PRIMARY KEY (agent_id));
CREATE NODE TABLE Skill (name STRING, path STRING, PRIMARY KEY (name));
CREATE NODE TABLE Tool (name STRING, PRIMARY KEY (name));

-- Relationships
CREATE REL TABLE SPAWNED (FROM Session TO Agent, FROM Agent TO Agent, prompt STRING, depth INT64, spawned_at TIMESTAMP);
CREATE REL TABLE LOADED (FROM Agent TO Skill, loaded_at TIMESTAMP);
CREATE REL TABLE INVOKED (FROM Agent TO Tool, tool_use_id STRING, tool_input STRING, start_ts TIMESTAMP, end_ts TIMESTAMP, duration_ms INT64, status STRING, tool_response STRING);
```

**Why Skill as node (not edge property):** Cross-session queries — "which agents loaded book2claude?" — require a shared node. Edge properties can't be traversed to. Given LadybugRAG's ontology patterns, nodes win.

**Why prompt as edge property (not Prompt node):** Prompts are metadata on transitions, not entities you traverse to. DuckDB handles full-text search on prompts via `regexp_matches` on the raw payload JSON column.

---

## 4. DuckDB Schema

```sql
CREATE TABLE events (
  event_id    VARCHAR PRIMARY KEY,
  received_at TIMESTAMPTZ NOT NULL,
  event_type  VARCHAR NOT NULL,
  session_id  VARCHAR,
  agent_id    VARCHAR,
  agent_type  VARCHAR,
  tool_use_id VARCHAR,
  tool_name   VARCHAR,
  cwd         VARCHAR,
  payload     JSON
);
CREATE INDEX idx_session   ON events(session_id);
CREATE INDEX idx_tool_pair ON events(tool_use_id) WHERE tool_use_id IS NOT NULL;
CREATE INDEX idx_type      ON events(event_type);
CREATE INDEX idx_time      ON events(received_at);
```

DuckDB is immutable source of truth. If LadybugDB gets corrupted, `scripts/replay.py` rebuilds it.

---

## 5. Docker Compose Stack

Claude Code runs on the host. Hooks POST to `localhost:4001`. All backend in Docker.

```yaml
services:
  collector:
    build: ./collector
    ports:
      - "4001:4001"   # hook ingestion
      - "4002:4002"   # dashboard API + SSE
    volumes:
      - ./data/duckdb:/data/duckdb
      - ./data/kuzu:/data/kuzu
    environment:
      DUCKDB_PATH: /data/duckdb/events.db
      KUZU_PATH: /data/kuzu
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4001/health"]
      interval: 10s
      timeout: 3s
      retries: 3

  dashboard:
    build: ./dashboard
    ports:
      - "3000:80"
    environment:
      PUBLIC_COLLECTOR_URL: http://localhost:4002
    depends_on:
      collector:
        condition: service_healthy
    restart: unless-stopped
```

**Why Docker over launchd:** Single `docker compose up -d` installs everything. Data volumes persist. `/observer:start` and `/observer:stop` commands manage it. No plist authoring, no Python environment management, reproducible across machines.

---

## 6. Plugin Structure

```
cc-observer/
├── .claude-plugin/
│   └── plugin.json
├── hooks/
│   └── hooks.json
├── commands/
│   ├── start.md          /observer:start
│   ├── stop.md           /observer:stop
│   ├── status.md         /observer:status
│   └── query.md          /observer:query [natural language]
├── skills/
│   └── observer-context/
│       └── SKILL.md
├── agents/
│   └── observer-analyst.md
├── .mcp.json             Kùzu MCP registration
├── collector/
│   ├── Dockerfile
│   ├── collector.py
│   ├── graph.py          LadybugDB mutations
│   ├── ledger.py         DuckDB writes
│   ├── nl_query.py       NL→Cypher via Anthropic API
│   └── requirements.txt
├── dashboard/
│   ├── Dockerfile
│   └── (SvelteKit app)
├── scripts/
│   ├── setup.sh          docker compose up + health check
│   ├── emit_event.py     command hook fallback (JSONL writer)
│   └── replay.py         rebuild Kùzu from DuckDB
├── data/                 gitignored
└── README.md
```

---

## 7. Hooks Configuration

```json
{
  "hooks": {
    "SessionStart":       [{"hooks": [{"type": "http", "url": "http://localhost:4001/events"}, {"type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/emit_event.py SessionStart"}]}],
    "SessionEnd":         [{"hooks": [{"type": "http", "url": "http://localhost:4001/events"}, {"type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/emit_event.py SessionEnd"}]}],
    "UserPromptSubmit":   [{"hooks": [{"type": "http", "url": "http://localhost:4001/events"}, {"type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/emit_event.py UserPromptSubmit"}]}],
    "SubagentStart":      [{"hooks": [{"type": "http", "url": "http://localhost:4001/events"}, {"type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/emit_event.py SubagentStart"}]}],
    "SubagentStop":       [{"hooks": [{"type": "http", "url": "http://localhost:4001/events"}, {"type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/emit_event.py SubagentStop"}]}],
    "Stop":               [{"hooks": [{"type": "http", "url": "http://localhost:4001/events"}, {"type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/emit_event.py Stop"}]}],
    "PreToolUse":         [{"matcher": ".*", "hooks": [{"type": "http", "url": "http://localhost:4001/events"}, {"type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/emit_event.py PreToolUse"}]}],
    "PostToolUse":        [{"matcher": ".*", "hooks": [{"type": "http", "url": "http://localhost:4001/events"}, {"type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/emit_event.py PostToolUse"}]}],
    "PostToolUseFailure": [{"matcher": ".*", "hooks": [{"type": "http", "url": "http://localhost:4001/events"}, {"type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/emit_event.py PostToolUseFailure"}]}],
    "PermissionRequest":  [{"hooks": [{"type": "http", "url": "http://localhost:4001/events"}]}],
    "Notification":       [{"hooks": [{"type": "http", "url": "http://localhost:4001/events"}]}],
    "PreCompact":         [{"hooks": [{"type": "http", "url": "http://localhost:4001/events"}]}]
  }
}
```

PermissionRequest/Notification/PreCompact are http-only — subprocess spawn during permission dialogs would block Claude visibly.

---

## 8. Plugin Components

### skills/observer-context/SKILL.md

Auto-loaded when context matches: "observer", "running agents", "execution graph", "tool latency", "spawn tree", "session history", "what claude is doing".

Teaches Claude:
- Full node/relationship schema with property types
- DuckDB vs LadybugDB routing rules
- Collector API endpoints
- Common Cypher patterns for live state
- `tool_use_id` correlation for span timing
- `/observer:query` command usage

### commands/start.md — `/observer:start`

Run `docker compose up -d` from `${CLAUDE_PLUGIN_ROOT}`. Poll `GET /health` until healthy (3 retries, 2s delay). Report: collector up, dashboard at `http://localhost:3000`, event count.

### commands/stop.md — `/observer:stop`

Run `docker compose down`. Confirm containers stopped. Note data is preserved.

### commands/status.md — `/observer:status`

Query `GET /health` and `GET /api/sessions/active`. Display: uptime, active sessions, running agents, events (total + last 5min), dashboard URL.

### commands/query.md — `/observer:query [question]`

POST `{"question": "$ARGUMENTS"}` to `http://localhost:4002/api/ask`. Present the generated Cypher, then results. Works for both natural language ("which agents are running?") and raw Cypher.

### agents/observer-analyst.md

Post-session summarizer. Invoked manually or wired to Stop hooks. Reads current session graph via Kùzu MCP tool calls. Produces: session duration, agent count, spawn tree depth, tool success rates, p95 latency, skills loaded, anomalies (long-running agents, repeated failures).

### .mcp.json — Kùzu MCP

```json
{
  "mcpServers": {
    "kuzu-observer": {
      "command": "uvx",
      "args": ["kuzu-mcp-server", "--db-path", "${CLAUDE_PLUGIN_ROOT}/data/kuzu"]
    }
  }
}
```

Gives Claude direct `mcp__kuzu-observer__query` tool for precise Cypher execution. The observer-analyst agent uses this. The NL query interface generates Cypher via Anthropic API, then executes via this tool.

---

## 9. NL→Cypher

`POST /api/ask` pipeline in the collector:

1. Receive `{question: string}`
2. Call `claude-sonnet-4-6` with schema-aware system prompt + recent session context
3. Model returns `{cypher, explanation}` as JSON
4. Execute Cypher against Kùzu
5. Return `{cypher, explanation, result}`

System prompt includes: full DDL, property types, status enums, 6 example question→Cypher pairs, instruction to return only JSON.

---

## 10. Collector API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/events` | Hook ingestion |
| `GET` | `/health` | Liveness + stats |
| `GET` | `/stream` | SSE for dashboard |
| `GET` | `/api/sessions` | All sessions paginated |
| `GET` | `/api/sessions/active` | Live sessions |
| `GET` | `/api/sessions/{id}/graph` | Cytoscape.js nodes+edges JSON |
| `GET` | `/api/sessions/{id}/timeline` | Gantt data |
| `GET` | `/api/events` | Raw DuckDB events |
| `POST` | `/api/ask` | NL→Cypher→result |
| `POST` | `/api/cypher` | Raw Cypher execution |
| `POST` | `/api/replay` | Rebuild Kùzu from DuckDB |

---

## 11. Build Phases

**Phase 1 — Docker Stack + Hook Plumbing**
Configure `docker-compose.yml`. FastAPI collector with DuckDB + Kùzu embedded. `setup.sh`. Dual hook delivery. Verify all 12 event types land in DuckDB.

**Phase 2 — Graph Materialization**
`graph.py` per-event mutations. Kùzu DDL on first start. `replay.py` recovery script. Validate with Cypher queries.

**Phase 3 — Plugin Shell**
`plugin.json`. Four commands. `observer-context` skill. `observer-analyst` agent. `.mcp.json`. `claude plugin add --path ./cc-observer`.

**Phase 4 — NL→Cypher**
`nl_query.py`. `POST /api/ask`. `/observer:query` wired to it. Test 20 representative questions.

**Phase 5 — Dashboard**
SvelteKit + nginx Dockerfile. All 6 views wired to SSE stream and REST API.
