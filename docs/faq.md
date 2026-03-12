---
title: FAQ
description: Frequently asked questions about CC Observer — installation, performance, data, querying, and extensibility
---

# FAQ

## Installation & Setup

### How do I install it?

Clone the repo, set your Anthropic API key, and run Docker Compose:

```bash
git clone https://github.com/halcyondude/observable-claude.git
cd observable-claude
export ANTHROPIC_API_KEY=sk-ant-...
docker compose up -d
```

Then install the plugin in Claude Code:

```bash
claude plugin add --path ./observable-claude
```

The hooks in `hooks/hooks.json` automatically capture events. No further configuration needed.

### Does it require Docker?

Yes. The collector (Python/FastAPI) and dashboard (SvelteKit/nginx) run as Docker containers. Docker Compose manages the stack. This avoids Python environment management, plist authoring, and ensures reproducibility across machines.

### What if I don't have an Anthropic API key?

The system works without one — everything except the NL-to-Cypher query feature (`/api/ask` and `/oc:query`). Event capture, graph materialization, the dashboard, and raw Cypher queries all work without an API key. The collector logs a warning at startup and the `/api/ask` endpoint returns an error response.

## Performance & Impact

### Does it affect Claude Code performance?

Negligibly. Hook delivery is non-blocking — HTTP POSTs to `localhost:4001` complete in single-digit milliseconds. The command fallback (`emit_event.py`) always exits 0 and never blocks Claude Code, even if the collector is down.

Three event types (PermissionRequest, Notification, PreCompact) are HTTP-only with no command fallback, because spawning a subprocess during permission dialogs would cause visible blocking.

### How much disk space does it use?

DuckDB grows with event count. A typical session with 500 events produces a database file around 1-5 MB. The LadybugDB graph directory is smaller — topology data is compact. Over weeks of daily use, expect tens of megabytes. DuckDB compresses well and the `events` table is append-only.

The `data/` directory is gitignored and survives `docker compose down`. Only `docker compose down -v` removes Docker volumes.

### How many SSE clients can connect?

The collector uses one `asyncio.Queue` (256 events max) per SSE client. For a single-user local tool, one or two clients (your dashboard tab, maybe a second monitor) is the expected load. There is no Redis pub/sub or message broker — this is intentionally simple for the local use case.

## Data Storage

### Where is the data stored?

All data stays on your local machine in the `data/` directory:

| Path | Contents |
|---|---|
| `data/duckdb/events.db` | DuckDB event ledger (immutable source of truth) |
| `data/ladybug/` | LadybugDB graph database directory |
| `data/fallback.jsonl` | Command fallback events (only written when HTTP delivery fails) |

These paths are mounted as Docker volumes. Data persists across container restarts.

### What's the difference between DuckDB and LadybugDB?

They solve different problems:

- **DuckDB** stores flat event rows. Use it for analytics, aggregation, time-range queries, and full-text search on payloads. It is the immutable source of truth.
- **LadybugDB** stores the labeled property graph (sessions, agents, tools, skills, and their relationships). Use it for topology queries: spawn trees, agent-tool relationships, path traversal.

If LadybugDB gets corrupted, it can be rebuilt from DuckDB using `scripts/replay.py` or `POST /api/replay`.

### Can I query the graph directly?

Yes, three ways:

1. **Dashboard Query Console** — type natural language or Cypher at `http://localhost:3000` (Query view)
2. **Plugin command** — `/oc:query which agents are running?` from Claude Code
3. **Raw API** — `POST http://localhost:4002/api/cypher` with `{"cypher": "MATCH (s:Session) RETURN s"}`
4. **MCP tool** — Claude Code can call `mcp__ladybug-observer__query` directly when the plugin is installed

### How do I rebuild the graph if it gets corrupted?

Two options:

```bash
# Option 1: API endpoint
curl -X POST http://localhost:4002/api/replay

# Option 2: CLI script
python scripts/replay.py
```

Both drop all LadybugDB tables, recreate them, and replay every event from DuckDB in chronological order. DuckDB is never modified — it's the source of truth.

## Usage

### What happens if the collector is down when Claude Code fires events?

Events go through the command fallback. `emit_event.py` writes the event to `data/fallback.jsonl` and attempts an HTTP POST with a 1-second timeout. If the POST fails, the JSONL line serves as a backup for later replay. The script always exits 0 — it never blocks Claude Code.

For the three HTTP-only events (PermissionRequest, Notification, PreCompact), events are silently dropped if the collector is down. These events are low-priority and stored in DuckDB only (no graph mutations).

### Can I use this with multiple Claude Code sessions?

Yes. Each session has a unique `session_id`. The collector handles concurrent sessions — events from different sessions are written to the same DuckDB and materialized into separate subgraphs in LadybugDB. The dashboard's Session History view lets you switch between sessions.

### Does this work in CI/CD?

It's designed for local development, not CI/CD. The Docker stack needs to be running, the hook configuration needs to be installed as a plugin, and the dashboard is served on localhost. You could potentially run the collector in a CI environment and capture events without the dashboard, but this is not a tested or supported use case.

## Querying

### How do I write custom Cypher queries?

Use the Query Console in Cypher mode, or POST to `/api/cypher`. The graph schema has four node types and three relationship types:

```cypher
-- Find all agents in a session with their spawn hierarchy
MATCH p = (s:Session)-[:SPAWNED*]->(a:Agent)
RETURN s.session_id, a.agent_id, a.agent_type, a.status

-- Tool latency by agent
MATCH (a:Agent)-[r:INVOKED]->(t:Tool)
WHERE r.duration_ms IS NOT NULL
RETURN a.agent_id, t.name, r.duration_ms
ORDER BY r.duration_ms DESC

-- Failed tool calls with full context
MATCH (a:Agent)-[r:INVOKED {status: 'failed'}]->(t:Tool)
RETURN a.agent_id, a.agent_type, t.name, r.tool_input, r.start_ts
```

The Query Console schema sidebar shows all available node labels, relationship types, and properties.

### How accurate is the NL-to-Cypher translation?

It uses `claude-sonnet-4-6` with a schema-aware system prompt and six example question-to-Cypher pairs. For common questions about running agents, spawn trees, tool failures, and latency, it produces correct Cypher consistently. Complex multi-hop traversals or unusual aggregations may need manual correction — switch to Cypher mode in the Query Console for precise control.

## Extensibility

### How do I extend this with new event types?

If Claude Code adds new hook event types, three changes are needed:

1. **`hooks/hooks.json`** — add the new event type with HTTP and (optionally) command delivery
2. **`collector/graph.py`** — add a handler function in the `_HANDLERS` dict if the event should produce graph mutations. For DuckDB-only events, add a no-op lambda.
3. **`collector/ledger.py`** — field extraction works generically via the nested/flat structure, so no changes needed unless the new event has unique fields worth indexing.

DuckDB captures the full payload JSON for every event regardless of type, so raw data is always available.

### How do I add a new dashboard view?

1. Create a new route in `dashboard/src/routes/{view-name}/+page.svelte`
2. Add the view to the sidebar navigation in `Sidebar.svelte`
3. Add the `Cmd+N` keyboard shortcut in the layout
4. Wire it to the appropriate data source (SSE store, REST endpoint, or both)

See [Contributing](contributing.md) for the full development setup.
