# CC Observer — Implementation Plan

> Ordered task breakdown for building the real-time execution graph monitor for Claude Code. Each task is a discrete unit of work with acceptance criteria and file outputs.

---

## Phase 1: Docker Stack + Hook Plumbing

**Goal:** A running Docker Compose stack with a FastAPI collector that accepts hook events, writes them to DuckDB, and streams them via SSE. Hooks are configured for dual delivery (http primary, command fallback).

### Task 1.1: Project Scaffolding

Create the directory structure from the plugin spec. Set up `.gitignore` for `data/`, `__pycache__/`, `node_modules/`, `.env`.

**Files to create:**
- `collector/` directory
- `collector/__init__.py`
- `collector/requirements.txt` — `fastapi`, `uvicorn`, `duckdb`, `real_ladybug`, `anthropic`, `httpx`
- `dashboard/` directory (empty for now)
- `scripts/` directory
- `data/` directory (gitignored)
- `hooks/` directory
- `commands/` directory
- `skills/` directory
- `agents/` directory
- `.gitignore`

**Acceptance criteria:**
- `git status` shows clean structure
- `pip install -r collector/requirements.txt` succeeds in a venv

---

### Task 1.2: DuckDB Ledger Module

Implement the DuckDB write layer. This is the immutable source of truth — every hook event gets a row.

**Files to create:**
- `collector/ledger.py`

**Implementation details:**
- `init_db(path: str) -> duckdb.DuckDBPyConnection` — creates the `events` table and indexes if not present (schema from Section 4 of the architecture spec)
- `write_event(conn, event: dict) -> str` — extracts `event_type`, `session_id`, `agent_id`, `agent_type`, `tool_use_id`, `tool_name`, `cwd` from the hook payload; generates `event_id` (UUID); sets `received_at` to `now()`; stores full payload as JSON column; returns `event_id`
- `query_events(conn, filters: dict, limit: int, offset: int) -> list[dict]` — parameterized query with optional filters on `event_type`, `session_id`, `agent_id`, `tool_use_id`; ordered by `received_at DESC`
- `get_sessions(conn) -> list[dict]` — `SELECT DISTINCT session_id, MIN(received_at), MAX(received_at), cwd FROM events GROUP BY session_id, cwd`
- `get_active_sessions(conn) -> list[dict]` — sessions with `SessionStart` but no `SessionEnd`

**Acceptance criteria:**
- Unit test: write 10 events, query by session_id, verify count and ordering
- Unit test: `get_sessions` returns correct aggregation
- DuckDB file is created at the configured path on first write

---

### Task 1.3: FastAPI Collector — Event Ingestion + Health

The core collector HTTP server. Two ports: 4001 for hook ingestion, 4002 for dashboard API and SSE. For simplicity, run a single Uvicorn process on 4002 and mount the ingestion endpoint on 4001 via a second ASGI app (or use a single app on one port with path routing — the Docker Compose `ports` mapping handles external exposure).

**Decision point:** Single Uvicorn process or two? Recommendation: single process, single FastAPI app. Map both 4001 and 4002 to the same container port (e.g., 8000). This avoids coordination complexity. The `docker-compose.yml` maps `4001:8000` and `4002:8000`. All endpoints live in one app.

**Files to create:**
- `collector/collector.py` — main FastAPI app
- `collector/Dockerfile`

**Endpoints (Phase 1):**
- `POST /events` — accepts hook payload JSON; calls `ledger.write_event()`; broadcasts to SSE subscribers; returns `{event_id, status: "ok"}`
- `GET /health` — returns `{status: "ok", events_total: N, uptime_seconds: N}`
- `GET /stream` — SSE endpoint; pushes every ingested event as `data: {json}\n\n` to connected clients
- `GET /api/sessions` — proxies to `ledger.get_sessions()`
- `GET /api/sessions/active` — proxies to `ledger.get_active_sessions()`
- `GET /api/events` — proxies to `ledger.query_events()` with query params for filters, limit, offset

**SSE implementation:**
- Use `asyncio.Queue` per connected client
- On `/events` POST, put event into all client queues
- On `/stream` GET, yield from the client's queue as SSE `data:` frames
- Include `event:` field set to `event_type` for client-side filtering

**Dockerfile:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "collector:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Acceptance criteria:**
- `curl -X POST localhost:4001/events -d '{"event_type":"SessionStart","session_id":"test-1","cwd":"/tmp"}' -H 'Content-Type: application/json'` returns 200 with `event_id`
- `curl localhost:4001/health` returns `events_total: 1`
- SSE client receives the event in real time
- DuckDB file contains the event row

---

### Task 1.4: Docker Compose Configuration

**Files to create:**
- `docker-compose.yml`

**Configuration:**
- `collector` service: build `./collector`, ports `4001:8000` and `4002:8000`, volumes for `./data/duckdb:/data/duckdb` and `./data/kuzu:/data/kuzu`, env vars `DUCKDB_PATH`, `KUZU_PATH`, `ANTHROPIC_API_KEY` (from host env), healthcheck on `/health`, restart `unless-stopped`
- `dashboard` service: stubbed out (build `./dashboard`, port `3000:80`, depends_on collector healthy) — commented out until Phase 5

**Acceptance criteria:**
- `docker compose up -d` starts the collector
- `docker compose ps` shows collector healthy
- Host can POST to `localhost:4001/events` and GET `localhost:4002/health`
- Data persists in `./data/` across container restarts

---

### Task 1.5: Setup and Teardown Scripts

**Files to create:**
- `scripts/setup.sh` — `docker compose up -d`, poll `/health` with 3 retries at 2s intervals, print status
- `scripts/teardown.sh` — `docker compose down`, confirm stopped

**Acceptance criteria:**
- `bash scripts/setup.sh` brings up the stack and reports healthy
- `bash scripts/teardown.sh` stops it cleanly
- Data directory survives teardown

---

### Task 1.6: Hook Configuration + Command Fallback

**Files to create:**
- `hooks/hooks.json` — dual delivery config for all 12 event types (per Section 7 of the architecture spec)
- `scripts/emit_event.py` — command fallback; reads event JSON from stdin, appends to `data/fallback.jsonl`; if collector is up, POSTs to `localhost:4001/events`

**Implementation details for `emit_event.py`:**
- Reads the hook payload from stdin (Claude Code pipes it)
- Writes to `data/fallback.jsonl` as append (atomic write with `\n` delimiter)
- Attempts HTTP POST to `http://localhost:4001/events` with 1s timeout
- If POST fails, the JSONL line is the backup (collector can replay later)
- Exits 0 always (never block Claude Code)

**Acceptance criteria:**
- `hooks.json` validates as JSON and matches all 12 event types from Section 2
- `echo '{"event_type":"SessionStart"}' | python scripts/emit_event.py SessionStart` writes to JSONL and POSTs to collector (if running)
- PermissionRequest, Notification, PreCompact are http-only (no command fallback)

---

### Task 1.7: End-to-End Smoke Test

No new files. Verify the full chain:

1. `bash scripts/setup.sh` — stack is up
2. Simulate a session: POST `SessionStart`, `SubagentStart`, `PreToolUse`, `PostToolUse`, `SubagentStop`, `SessionEnd` to `localhost:4001/events`
3. `GET /api/sessions` returns the session
4. `GET /api/events?session_id=X` returns all 6 events in order
5. SSE client received all 6 events
6. `bash scripts/teardown.sh` — stack is down
7. `bash scripts/setup.sh` — stack is back up, DuckDB still has the 6 events

**Acceptance criteria:**
- All 7 steps pass
- Write a test script: `scripts/smoke_test.sh`

---

## Phase 2: Graph Materialization

**Goal:** Every ingested event triggers the appropriate Cypher mutation in LadybugDB. The graph stays in sync with the event ledger. A replay script can rebuild the graph from scratch.

**Dependency:** Phase 1 complete (collector running, DuckDB working).

### Task 2.1: LadybugDB DDL Initialization

**Files to create:**
- `collector/graph.py`

**Implementation details:**
- `init_graph(db_path: str) -> Database` — opens LadybugDB at path; runs DDL to create all 4 node tables (`Session`, `Agent`, `Skill`, `Tool`) and 3 relationship tables (`SPAWNED`, `LOADED`, `INVOKED`) if they don't exist; returns database handle
- DDL exactly as specified in Section 3 of the architecture spec
- Must be idempotent — safe to call on an already-initialized database

**Technical decision: LadybugDB API surface.** LadybugDB wraps Kuzu. Verify the exact Python API: `from real_ladybug import Database` or similar. The `pip install real_ladybug` package may expose a different interface than raw Kuzu. This needs to be confirmed at implementation time by reading the LadybugDB source/docs.

**Acceptance criteria:**
- `init_graph()` creates all tables on a fresh database
- Calling `init_graph()` again on the same database does not error
- Cypher `MATCH (n) RETURN labels(n)` returns empty results (tables exist, no data)

---

### Task 2.2: Per-Event Cypher Mutations

**Files to modify:**
- `collector/graph.py` — add `materialize_event(db, event: dict)` function

**Mutation mapping (from Section 2 of the architecture spec):**

| Event | Cypher Mutation |
|---|---|
| `SessionStart` | `CREATE (s:Session {session_id: $sid, cwd: $cwd, start_ts: $ts})` |
| `SessionEnd` | `MATCH (s:Session {session_id: $sid}) SET s.end_ts = $ts` |
| `SubagentStart` | `CREATE (a:Agent {agent_id: $aid, agent_type: $atype, session_id: $sid, start_ts: $ts, status: 'running'})` + `MERGE` parent node + `CREATE (parent)-[:SPAWNED {prompt: $prompt, depth: $depth, spawned_at: $ts}]->(a)` |
| `SubagentStop` | `MATCH (a:Agent {agent_id: $aid}) SET a.end_ts = $ts, a.status = $status` |
| `Stop` | `MATCH (a:Agent {agent_id: $aid}) SET a.status = 'complete'` |
| `PreToolUse` | `MERGE (t:Tool {name: $tool_name})` + `MATCH (a:Agent {agent_id: $aid})` + `CREATE (a)-[:INVOKED {tool_use_id: $tuid, tool_input: $input, start_ts: $ts, status: 'pending'}]->(t)` |
| `PostToolUse` | `MATCH (a:Agent)-[r:INVOKED {tool_use_id: $tuid}]->(t:Tool) SET r.end_ts = $ts, r.duration_ms = $dur, r.status = 'success', r.tool_response = $resp` |
| `PostToolUseFailure` | Same as PostToolUse but `r.status = 'failed'` |
| `UserPromptSubmit` | Store prompt text as edge property on most recent SPAWNED edge for the agent |
| `Notification`, `PermissionRequest` | DuckDB only — no graph mutation |
| `PreCompact` | DuckDB only (future: graph snapshot) |

**Handling SPAWNED edge parent resolution for `SubagentStart`:**
- The hook payload includes `agent_id` of the new agent. The parent may be the session root or another agent.
- If the payload includes a parent `agent_id`, create `(parent:Agent)-[:SPAWNED]->(child:Agent)`
- If no parent agent (depth 0), create `(s:Session)-[:SPAWNED]->(a:Agent)`
- Need to inspect actual Claude Code hook payloads to confirm which fields carry parent info. **This is a risk — the hook payload schema for SubagentStart may not include an explicit parent_agent_id.** Mitigation: inspect real payloads in Phase 1 smoke test; adjust mutation logic accordingly.

**Files to modify:**
- `collector/collector.py` — after `ledger.write_event()`, call `graph.materialize_event()`

**Acceptance criteria:**
- Replay the Phase 1 smoke test sequence; verify graph contains: 1 Session, 1 Agent, 1 Tool, SPAWNED edge, INVOKED edge
- `MATCH (s:Session)-[:SPAWNED]->(a:Agent)-[:INVOKED]->(t:Tool) RETURN s, a, t` returns the expected row
- Agent status transitions correctly: running -> complete

---

### Task 2.3: Graph Query Endpoints

**Files to modify:**
- `collector/collector.py` — add graph-serving endpoints

**Endpoints:**
- `GET /api/sessions/{id}/graph` — returns Cytoscape.js-compatible JSON: `{nodes: [{data: {id, label, ...}}], edges: [{data: {source, target, ...}}]}`
  - Query: `MATCH (s:Session {session_id: $sid})-[*1..10]->(n) RETURN n` + relationships
  - Transform LadybugDB results into Cytoscape elements format
- `GET /api/sessions/{id}/timeline` — returns Gantt-compatible JSON: array of `{agent_id, agent_type, start_ts, end_ts, status, depth, tool_events: [{tool_use_id, tool_name, start_ts, end_ts, status}]}`
  - Query: all Agents for session + their INVOKED edges

**Acceptance criteria:**
- `/graph` endpoint returns valid Cytoscape.js JSON with correct node/edge structure
- `/timeline` endpoint returns agents with their tool events nested
- Both endpoints return empty arrays for non-existent session (not 404)

---

### Task 2.4: Replay Script

**Files to create:**
- `scripts/replay.py`

**Implementation:**
- Reads all events from DuckDB ordered by `received_at ASC`
- Drops and recreates all LadybugDB tables (clean slate)
- Iterates events, calling `graph.materialize_event()` for each
- Prints progress: `Replayed N events, created X nodes, Y edges`
- Exposes as both CLI (`python scripts/replay.py`) and API endpoint (`POST /api/replay`)

**Acceptance criteria:**
- Delete the Kuzu data directory, run replay, verify graph matches original
- Replay is idempotent — running twice produces the same graph
- Works on a DuckDB with 1000+ events (performance sanity check)

---

## Phase 3: Plugin Shell

**Goal:** CC Observer is installable as a Claude Code plugin with commands, a skill, an agent, and MCP server registration.

**Dependency:** Phase 2 complete (collector + graph working).

### Task 3.1: Plugin Manifest

**Files to create:**
- `.claude-plugin/plugin.json`

**Contents:**
```json
{
  "name": "cc-observer",
  "version": "0.1.0",
  "description": "Real-time execution graph monitoring for Claude Code",
  "commands": ["commands/*.md"],
  "hooks": "hooks/hooks.json",
  "skills": ["skills/*/SKILL.md"],
  "agents": ["agents/*.md"]
}
```

**Technical decision:** The exact `plugin.json` schema depends on the Claude Code plugin system version. The structure above follows the pattern from the architecture spec. Verify against current Claude Code plugin documentation at implementation time.

**Acceptance criteria:**
- `claude plugin add --path .` succeeds (or equivalent install command)
- Plugin appears in `claude plugin list`

---

### Task 3.2: Commands

**Files to create:**
- `commands/start.md` — `/observer:start`: runs `bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh`, reports status
- `commands/stop.md` — `/observer:stop`: runs `bash ${CLAUDE_PLUGIN_ROOT}/scripts/teardown.sh`, confirms stopped
- `commands/status.md` — `/observer:status`: queries `GET /health` and `GET /api/sessions/active`, displays uptime, active sessions, agent count, event count, dashboard URL
- `commands/query.md` — `/observer:query [question]`: POSTs question to `http://localhost:4002/api/ask`, displays generated Cypher + results

**Acceptance criteria:**
- Each command executes the correct action when invoked from Claude Code
- `/observer:start` waits for healthy before reporting success
- `/observer:query "which agents are running?"` returns results (requires Phase 4 for NL; raw Cypher works now)

---

### Task 3.3: Skill — Observer Context

**Files to create:**
- `skills/observer-context/SKILL.md`

**Contents:** Teaches Claude about the CC Observer system:
- Full node/relationship schema with property types and enums
- When to use DuckDB (raw events, full-text, aggregations) vs LadybugDB (graph traversal, relationships, topology)
- Collector API endpoints with request/response examples
- Common Cypher patterns: find running agents, get spawn tree, calculate tool latency, find failures
- Correlation model: `tool_use_id` links PreToolUse → PostToolUse for span timing
- Available commands: `/observer:start`, `/observer:stop`, `/observer:status`, `/observer:query`

**Context match triggers:** "observer", "running agents", "execution graph", "tool latency", "spawn tree", "session history", "what claude is doing"

**Acceptance criteria:**
- Skill loads when Claude detects relevant context
- Claude can answer "how do I query for running agents?" using skill knowledge

---

### Task 3.4: Agent — Observer Analyst

**Files to create:**
- `agents/observer-analyst.md`

**Agent prompt:** Post-session summarizer. Uses `mcp__kuzu-observer__query` tool to read the session graph. Produces a structured report:
- Session duration
- Agent count and max spawn depth
- Spawn tree structure (text representation)
- Tool success rates per tool name
- p95 and p50 latency per tool
- Skills loaded across agents
- Anomalies: agents that ran >2x the median duration, tools with >10% failure rate, agents that failed

**Acceptance criteria:**
- Agent can be invoked manually from Claude Code
- Report covers all specified metrics
- Agent uses MCP tool calls (not HTTP) to query the graph

---

### Task 3.5: MCP Server Registration

**Files to create:**
- `.mcp.json`

**Contents:**
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

**Risk:** The `kuzu-mcp-server` package must be compatible with LadybugDB's Kuzu fork. If LadybugDB modifies the storage format, the standard Kuzu MCP server may not read it. **Mitigation:** Test early. If incompatible, write a thin MCP server wrapper that uses `real_ladybug` directly — this would be a new task.

**Acceptance criteria:**
- `mcp__kuzu-observer__query` tool appears in Claude Code's tool list when plugin is installed
- `mcp__kuzu-observer__query("MATCH (s:Session) RETURN s.session_id")` returns session data

---

## Phase 4: NL→Cypher

**Goal:** Natural language questions about the execution graph get translated to Cypher via the Anthropic API, executed, and returned with explanations.

**Dependency:** Phase 2 (graph populated), Phase 3 (MCP server working for validation).

### Task 4.1: NL→Cypher Module

**Files to create:**
- `collector/nl_query.py`

**Implementation:**
- `translate(question: str, schema: str, session_context: str) -> dict` — calls `claude-sonnet-4-6` via the Anthropic Python SDK
- System prompt includes:
  - Full DDL (all CREATE statements from Section 3)
  - Property types and status enums (`running`, `complete`, `failed`, `pending`, `success`)
  - 6+ example question→Cypher pairs (from Section 9 / skill content)
  - Instruction to return JSON: `{"cypher": "...", "explanation": "..."}`
  - Current session_id for context scoping
- Uses `anthropic.Anthropic()` client with `ANTHROPIC_API_KEY` from env
- Parses response JSON; if parsing fails, returns error with raw response

**Example question→Cypher pairs to include in system prompt:**
1. "Which agents are currently running?" → `MATCH (a:Agent {status: 'running'}) RETURN a.agent_id, a.agent_type, a.start_ts`
2. "Show me the spawn tree" → `MATCH (s:Session)-[:SPAWNED*]->(a:Agent) RETURN s, a`
3. "What tool calls failed?" → `MATCH (a:Agent)-[r:INVOKED {status: 'failed'}]->(t:Tool) RETURN a.agent_id, t.name, r.tool_use_id`
4. "Which agent has been running the longest?" → `MATCH (a:Agent {status: 'running'}) RETURN a.agent_id, a.agent_type, a.start_ts ORDER BY a.start_ts ASC LIMIT 1`
5. "What skills were loaded this session?" → `MATCH (a:Agent)-[:LOADED]->(s:Skill) RETURN DISTINCT s.name`
6. "What was the slowest tool call?" → `MATCH (a:Agent)-[r:INVOKED]->(t:Tool) RETURN t.name, r.duration_ms, a.agent_id ORDER BY r.duration_ms DESC LIMIT 1`

**Acceptance criteria:**
- Given a natural language question, returns valid Cypher that executes without error
- Explanation is a plain-English sentence describing the query
- Handles questions outside the schema gracefully (returns error, not hallucinated Cypher)

---

### Task 4.2: Ask + Cypher Endpoints

**Files to modify:**
- `collector/collector.py` — add endpoints

**Endpoints:**
- `POST /api/ask` — accepts `{question: string}`; calls `nl_query.translate()`, executes resulting Cypher against LadybugDB, returns `{cypher, explanation, result}`
- `POST /api/cypher` — accepts `{cypher: string}`; executes directly against LadybugDB, returns `{result}` or `{error}`

**Error handling:**
- If NL translation fails: return `{error: "Failed to generate Cypher", details: ...}`
- If Cypher execution fails: return `{error: "Query execution failed", cypher: ..., details: ...}`
- Both endpoints return 200 with error payloads (not 500) — the dashboard handles display

**Acceptance criteria:**
- `POST /api/ask {"question": "which agents are running?"}` returns Cypher + results
- `POST /api/cypher {"cypher": "MATCH (s:Session) RETURN s"}` returns session data
- Invalid Cypher returns a structured error, not a 500

---

### Task 4.3: Validate with Representative Questions

No new files. Test the NL→Cypher pipeline against 20 representative questions spanning:
- Live state queries ("what's running right now?")
- Historical queries ("what happened in the last session?")
- Aggregation queries ("which tool has the highest failure rate?")
- Topology queries ("show me the full spawn tree")
- Performance queries ("what's the p95 tool latency?")

**Acceptance criteria:**
- 16/20 questions produce correct, executable Cypher
- Document the 4 (or fewer) that fail with notes on why and whether they're fixable via prompt tuning
- Write results to `docs/nl-query-validation.md`

---

## Phase 5: Dashboard

**Goal:** SvelteKit dashboard with all 6 views, consuming SSE and REST endpoints from the collector.

**Dependency:** Phase 2 (graph + timeline endpoints), Phase 4 (ask + cypher endpoints).

### Task 5.1: SvelteKit Project Scaffolding

**Files to create:**
- `dashboard/` — full SvelteKit project via `npx create-svelte@latest`
- `dashboard/package.json` — dependencies: `cytoscape`, `cytoscape-dagre`, `tailwindcss`
- `dashboard/Dockerfile` — multi-stage build: Node for build, nginx for serve
- `dashboard/nginx.conf` — serves SvelteKit static build, proxies `/api/*` and `/stream` to collector
- `dashboard/tailwind.config.ts` — design tokens from Section 4 of the UI spec
- `dashboard/src/app.css` — CSS custom properties for all design tokens

**Dockerfile:**
```dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

**nginx.conf key routes:**
- `/api/*` → proxy to `collector:8000`
- `/stream` → proxy to `collector:8000` (SSE — needs `proxy_buffering off`)
- `/*` → serve static SvelteKit build

**Acceptance criteria:**
- `docker compose up -d` starts both collector and dashboard
- `http://localhost:3000` serves the SvelteKit app
- `/api/health` proxied through nginx returns collector health

---

### Task 5.2: Shared Layout + Navigation

**Files to create:**
- `dashboard/src/routes/+layout.svelte` — persistent top bar + sidebar
- `dashboard/src/lib/components/TopBar.svelte` — wordmark, active session display, connection status pill, agent count badge
- `dashboard/src/lib/components/Sidebar.svelte` — 6 nav items with icons, active indicator, collapsible, badges (agent count on Spawn Tree, unread count on Tool Feed)
- `dashboard/src/lib/stores/session.ts` — Svelte store for active session state
- `dashboard/src/lib/stores/connection.ts` — SSE connection state (connected/reconnecting/disconnected)

**Responsive behavior:**
- Below 960px: sidebar collapses to icon-only (56px)
- Sidebar toggle button at bottom

**Acceptance criteria:**
- Layout renders with top bar and sidebar
- Navigation between 6 view routes works
- Connection status reflects actual SSE state
- Sidebar collapses at narrow widths

---

### Task 5.3: SSE Client + Event Store

**Files to create:**
- `dashboard/src/lib/services/sse.ts` — SSE client with reconnection (exponential backoff: 1s, 2s, 4s, 8s, max 30s)
- `dashboard/src/lib/stores/events.ts` — Svelte writable store for live event stream; ring buffer (last 10,000 events)

**Implementation:**
- `EventSource` connection to `http://localhost:4002/stream` (via nginx proxy as `/stream`)
- On message: parse JSON, push to event store, update connection status
- On disconnect: trigger reconnect with backoff; on reconnect, re-fetch session graph to fill gaps
- After 5 failed reconnects: stop retrying, show manual retry button

**Acceptance criteria:**
- Events appear in the store within 100ms of being POSTed to the collector
- Disconnecting the collector triggers reconnect behavior
- Reconnecting re-fetches current session state

---

### Task 5.4: View 1 — Spawn Tree

**Files to create:**
- `dashboard/src/routes/tree/+page.svelte`
- `dashboard/src/lib/components/SpawnTree.svelte` — Cytoscape.js canvas wrapper
- `dashboard/src/lib/components/NodeDetail.svelte` — slide-in panel (320px) for selected node

**Implementation:**
- Fetch graph from `GET /api/sessions/{id}/graph`
- Cytoscape.js with dagre layout (top-to-bottom)
- Node styling per UI spec: rounded rectangles, color by status (teal=running, dark gray=complete, coral=failed, navy=session root), size proportional to tool call count
- Edge styling: directed arrows, teal, 1.5px, prompt text on hover
- Live updates via SSE: new nodes animate in from parent position
- Running nodes: subtle 2s pulse animation on border
- Completed agents fade to gray
- Failed agents flash coral briefly
- Auto-layout unless user has panned; "Reset" button restores auto-layout
- Click node: slide-in panel with full agent details (agent_id, type, status, duration, spawned_by, prompt, tools invoked, skills loaded)
- Floating controls: zoom in/out/fit/reset
- Floating legend: node color meanings

**Acceptance criteria:**
- Graph renders with correct node colors and layout
- New agents appear in real time
- Node detail panel shows complete agent information
- Layout respects manual pan/zoom

---

### Task 5.5: View 2 — Timeline (Gantt)

**Files to create:**
- `dashboard/src/routes/timeline/+page.svelte`
- `dashboard/src/lib/components/GanttChart.svelte`

**Implementation:**
- Fetch data from `GET /api/sessions/{id}/timeline`
- Left column (200px): agent labels, indented by spawn depth (16px per level)
- Right area: horizontal bars on shared time axis
- Bar colors: teal (running, right edge animated), dark gray (complete), coral (failed, X icon)
- Time axis auto-scales to session duration (1s, 5s, 30s, 1m, 5m intervals)
- Current time indicator: thin teal vertical line at right edge, moves live
- Tool call tick marks on bars: 2px wide x 12px tall, teal for success, coral for failure
- Hover tooltip: agent_id, start time, duration, status, prompt preview
- Hover on tick: tool_name, duration, input summary
- Auto-scroll to show newest agents unless user has scrolled manually
- Canvas-based rendering (or SVG) for performance with many agents

**Acceptance criteria:**
- Bars render at correct positions relative to session start time
- Running bars grow in real time
- Tool call ticks appear on bars
- Time axis scales appropriately

---

### Task 5.6: View 3 — Tool Feed

**Files to create:**
- `dashboard/src/routes/tools/+page.svelte`
- `dashboard/src/lib/components/ToolFeed.svelte`
- `dashboard/src/lib/components/EventRow.svelte` — single event row (collapsed 48px, expandable)

**Implementation:**
- Reverse chronological list from SSE event store (filtered to PreToolUse, PostToolUse, PostToolUseFailure)
- Event row: 4px colored left border (teal=Pre, green=Post, coral=Failure), timestamp (HH:MM:SS.mmm), event type pill, tool name (bold), agent type (muted), duration (right-aligned, PostToolUse only), summary line
- Click to expand: full tool_input as syntax-highlighted JSON, tool_response (truncated 500 chars with "show more"), correlation IDs
- Filter bar: event type multi-select pills, tool name autocomplete, status filter
- Pause button: freezes scroll; auto-pause when user scrolls up
- New events prepend at top with subtle slide-in animation

**Acceptance criteria:**
- Events appear in real time from SSE
- Filters work without page reload
- Expanded rows show formatted JSON
- Pause stops scroll jank when reading

---

### Task 5.7: View 4 — Analytics

**Files to create:**
- `dashboard/src/routes/analytics/+page.svelte`
- `dashboard/src/lib/components/StatCard.svelte`
- `dashboard/src/lib/components/LatencyChart.svelte`
- `dashboard/src/lib/components/EventRateChart.svelte`
- `dashboard/src/lib/components/ToolTable.svelte`

**Implementation:**
- 4 stat cards (responsive grid: 4-across > 1200px, 2x2 900-1200px, 1-col < 900px):
  - Total Events (count + delta)
  - Active Agents (live + completed today)
  - Tool Success Rate (% with color coding)
  - Median Tool Latency (p50 + p95 below)
- Tool latency horizontal bar chart: p50 bar + p95 segment, color-coded by speed tier
- Event rate area chart: events per 10s bucket, stacked by event type
- Per-tool table: tool name, calls (success/fail), latency p50/p95, sortable columns
- Time range selector: Last 5m / 30m / 1h / Session / All time
- Data from `GET /api/events` with appropriate query params; aggregation done client-side or via additional DuckDB analytic endpoints

**Technical decision:** Client-side vs server-side aggregation. For v0.1, aggregate client-side from the events endpoint. If performance is poor with large event sets, add dedicated DuckDB analytic query endpoints in a follow-up.

**Acceptance criteria:**
- Stat cards show live-updating values
- Charts render with correct data
- Time range selector changes the data window
- Table is sortable

---

### Task 5.8: View 5 — Query Console

**Files to create:**
- `dashboard/src/routes/query/+page.svelte`
- `dashboard/src/lib/components/QueryConsole.svelte`
- `dashboard/src/lib/components/ResultsTable.svelte`
- `dashboard/src/lib/components/ResultsGraph.svelte` — mini Cytoscape for graph results

**Implementation:**
- Mode toggle: "Natural Language" / "Cypher"
- NL mode: text input with placeholder examples, "Ask" button (Cmd+Enter), shows generated Cypher in collapsible code block, explanation line, results
- Cypher mode: code editor with syntax highlighting (CodeMirror or Monaco), schema sidebar (collapsible, shows all node labels, relationship types, properties)
- Results: table for tabular results (sortable, copy-to-CSV), mini Cytoscape canvas for graph results
- Example query chips in NL mode (5 pre-loaded from UI spec)
- Query history: last 20 queries in localStorage, accessible via dropdown
- Loading state: spinner in Ask button, skeleton rows in results
- Error state: show error message + offer retry

**Acceptance criteria:**
- NL question returns Cypher + results + explanation
- Raw Cypher executes and displays results
- Graph results render as mini Cytoscape
- Query history persists across page reloads

---

### Task 5.9: View 6 — Session History

**Files to create:**
- `dashboard/src/routes/sessions/+page.svelte`
- `dashboard/src/lib/components/SessionList.svelte`
- `dashboard/src/lib/components/SessionDetail.svelte`

**Implementation:**
- Left panel (320px): session list from `GET /api/sessions`, sorted newest first
- Session list item: status indicator (green=active, gray=completed), cwd (last segment bold, full path below), metadata (start time, duration, agent count, event count), active session highlighted with teal border + LIVE badge
- Clicking a session switches all views to that session's data (via session store)
- Archive banner: "Viewing archived session — [session_id] [date]" with "Return to live" button
- Past sessions show final state in other views (all agents complete)

**Acceptance criteria:**
- Session list loads and shows all sessions
- Clicking a past session switches context in all views
- "Return to live" switches back to active session
- Active session has LIVE badge

---

### Task 5.10: Keyboard Navigation

**Files to modify:**
- `dashboard/src/routes/+layout.svelte` — global keyboard handler

**Shortcuts per UI spec:**
- `Cmd+1` through `Cmd+6`: switch views
- `Cmd+Enter`: submit query (Query Console)
- `Escape`: close slide-in panels, collapse expanded rows
- `Space`: toggle pause (Tool Feed)
- `/`: focus query input (Query Console)

**Acceptance criteria:**
- All shortcuts work from any view (except view-specific ones)
- Shortcuts don't conflict with browser defaults

---

### Task 5.11: Docker Integration + Final Wiring

**Files to modify:**
- `docker-compose.yml` — uncomment dashboard service
- `dashboard/Dockerfile` — finalize multi-stage build
- `dashboard/nginx.conf` — finalize proxy config

**Acceptance criteria:**
- `docker compose up -d` starts both services
- Dashboard loads at `localhost:3000`
- All 6 views populated with data from a live Claude Code session
- SSE reconnection works after collector restart

---

## Cross-Cutting Concerns

### Testing Strategy

- **Phase 1-2:** Python unit tests for `ledger.py` and `graph.py` using pytest. Integration test via `smoke_test.sh`.
- **Phase 3:** Manual testing via Claude Code plugin installation.
- **Phase 4:** NL→Cypher validation documented in `docs/nl-query-validation.md`.
- **Phase 5:** Manual testing of all 6 views. Consider Playwright for critical paths in a follow-up.

### Error Handling

- Collector must never crash on malformed hook payloads — log and continue
- DuckDB writes are the priority; if LadybugDB mutation fails, log the error but don't lose the event
- SSE disconnects are expected — the dashboard reconnection logic is critical path

### Performance Considerations

- DuckDB handles analytical queries well, but the events table will grow unboundedly. Add a retention/archival strategy post-v0.1.
- LadybugDB graph size depends on session count. Replay script becomes slow with large histories. Consider incremental replay.
- SSE fan-out: for a single-user local tool, one or two SSE clients is the expected load. No need for Redis pub/sub.

### Security

- All traffic is localhost-only. No auth required for v0.1.
- `ANTHROPIC_API_KEY` is passed via environment variable, never written to config files or Docker images.
- Hook payloads may contain sensitive code content (tool inputs/outputs). Data stays local in `./data/`.

---

## Risks and Unknowns

| Risk | Impact | Mitigation |
|---|---|---|
| LadybugDB Python API differs from raw Kuzu | Phase 2 blocked | Read `real_ladybug` source at implementation start; adjust `graph.py` accordingly |
| `kuzu-mcp-server` incompatible with LadybugDB storage format | Phase 3 MCP broken | Test early; fallback is a thin custom MCP server using `real_ladybug` directly |
| Claude Code hook payload schema undocumented | Phase 1-2 wrong field extraction | Capture real payloads in Phase 1 smoke test; adjust field mapping |
| `SubagentStart` payload lacks explicit parent_agent_id | SPAWNED edges wrong | Inspect payloads; may need to infer parent from session state or agent_id hierarchy |
| NL→Cypher accuracy on complex queries | Phase 4 UX degraded | Prompt tuning + fallback to raw Cypher mode in dashboard |
| SvelteKit + Cytoscape.js SSR compatibility | Phase 5 build issues | Use dynamic imports for Cytoscape (browser-only); disable SSR for graph views |

---

## Dependency Graph

```
Phase 1: Docker + Hooks
  1.1 Scaffolding
  1.2 DuckDB Ledger ──────────────────┐
  1.3 Collector (depends on 1.2) ─────┤
  1.4 Docker Compose (depends on 1.3) ┤
  1.5 Scripts (depends on 1.4) ───────┤
  1.6 Hooks (parallel with 1.3-1.5) ──┤
  1.7 Smoke Test (depends on all) ────┘

Phase 2: Graph (depends on Phase 1)
  2.1 DDL Init ──────────────────┐
  2.2 Mutations (depends on 2.1) ┤
  2.3 Query Endpoints (dep 2.2) ─┤
  2.4 Replay (depends on 2.2) ───┘

Phase 3: Plugin (depends on Phase 2)
  3.1 Manifest ──────────────┐
  3.2 Commands (dep 3.1) ────┤
  3.3 Skill (parallel) ──────┤
  3.4 Agent (dep 3.3, 3.5) ──┤
  3.5 MCP Server (dep 3.1) ──┘

Phase 4: NL→Cypher (depends on Phase 2; parallel with Phase 3)
  4.1 Translation Module ────┐
  4.2 Endpoints (dep 4.1) ───┤
  4.3 Validation (dep 4.2) ──┘

Phase 5: Dashboard (depends on Phase 2 + Phase 4)
  5.1 Scaffolding ────────────────────┐
  5.2 Layout + Nav (dep 5.1) ─────────┤
  5.3 SSE Client (dep 5.1) ──────────┤
  5.4 Spawn Tree (dep 5.2, 5.3) ─────┤
  5.5 Timeline (dep 5.2, 5.3) ───────┤  ← 5.4-5.9 can be
  5.6 Tool Feed (dep 5.2, 5.3) ──────┤    parallelized across
  5.7 Analytics (dep 5.2, 5.3) ──────┤    developers
  5.8 Query Console (dep 5.2, 5.3) ──┤
  5.9 Session History (dep 5.2, 5.3) ┤
  5.10 Keyboard Nav (dep 5.2) ───────┤
  5.11 Docker Integration (dep all) ──┘
```

Phases 3 and 4 can run in parallel. Phase 5 views (5.4-5.9) can be parallelized across developers or agents once the shared infrastructure (5.1-5.3) is complete.
