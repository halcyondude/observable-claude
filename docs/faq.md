---
title: FAQ
description: Frequently asked questions about CC Observer — installation, performance, data, querying, and extensibility
---

# FAQ

## Installation & Setup

### How do I install it?

```bash
git clone https://github.com/halcyondude/observable-claude.git
cd observable-claude
export ANTHROPIC_API_KEY=sk-ant-...
docker compose up -d
```

Then install the plugin:

```bash
claude plugin add --path ./observable-claude
```

The hooks in `hooks/hooks.json` capture events automatically. Nothing else to configure.

### Does it require Docker?

Yes. Collector (Python/FastAPI) and dashboard (SvelteKit/nginx) run as Docker containers. Docker Compose manages the stack. Avoids Python env management and plist authoring, ensures reproducibility across machines.

### What if I don't have an Anthropic API key?

Everything works except NL-to-Cypher (`/api/ask` and `/oc:query`). Event capture, graph materialization, dashboard, raw Cypher queries — all fine without a key. Collector logs a warning at startup; `/api/ask` returns an error.

## Performance & Impact

### Does it affect Claude Code performance?

Negligibly. HTTP POSTs to `localhost:4001` complete in single-digit milliseconds. The command fallback always exits 0 and never blocks, even if the collector is down.

Three events (PermissionRequest, Notification, PreCompact) are HTTP-only — no command fallback because subprocess spawn during permission dialogs causes visible blocking.

### How much disk space?

DuckDB grows with event count. ~500 events = 1-5 MB. LadybugDB is smaller (topology data is compact). Weeks of daily use = tens of megabytes. DuckDB compresses well.

`data/` is gitignored, survives `docker compose down`. Only `docker compose down -v` removes Docker volumes.

### How many SSE clients?

One `asyncio.Queue` (256 events max) per client. For a single-user local tool, one or two clients is the expected load. No Redis, no message broker — intentionally simple.

## Data Storage

### Where is the data?

All local, in `data/`:

| Path | Contents |
|---|---|
| `data/duckdb/events.db` | DuckDB event ledger (source of truth) |
| `data/ladybug/` | LadybugDB graph database |
| `data/fallback.jsonl` | Fallback events (only when HTTP fails) |

Docker volume mounts. Data persists across restarts.

### DuckDB vs LadybugDB?

Different problems:

- **DuckDB** — flat event rows. Analytics, aggregation, time-range queries, full-text search. Immutable source of truth.
- **LadybugDB** — labeled property graph. Spawn trees, agent-tool relationships, path traversal.

LadybugDB corrupted? Rebuild from DuckDB: `scripts/replay.py` or `POST /api/replay`.

### Can I query the graph directly?

Four ways:

1. **Dashboard Query Console** — NL or Cypher at `localhost:3000`
2. **Plugin command** — `/oc:query which agents are running?`
3. **Raw API** — `POST localhost:4002/api/cypher` with `{"cypher": "MATCH ..."}`
4. **MCP tool** — `mcp__ladybug-observer__query` from Claude Code

### How do I rebuild a corrupted graph?

```bash
# API endpoint
curl -X POST http://localhost:4002/api/replay

# CLI script
python scripts/replay.py
```

Both drop all LadybugDB tables, recreate, replay every event from DuckDB chronologically. DuckDB is never modified.

## Usage

### What if the collector is down?

Events go through the command fallback. `emit_event.py` writes to `data/fallback.jsonl` and retries HTTP with a 1s timeout. Always exits 0.

The three HTTP-only events (PermissionRequest, Notification, PreCompact) are silently dropped when the collector is down. Low-priority, DuckDB-only, no graph mutations.

### Multiple concurrent sessions?

Yes. Each session has a unique `session_id`. The collector handles concurrent sessions — events go to the same DuckDB, materialize into separate LadybugDB subgraphs. Session History view lets you switch between them.

### CI/CD support?

Designed for local dev, not CI. Needs Docker running, plugin installed, dashboard on localhost. You could run the collector headless in CI and capture events, but that's not a tested use case.

## Querying

### Custom Cypher queries?

Query Console in Cypher mode, or `POST /api/cypher`. Four node types, three relationship types:

```cypher
-- Spawn hierarchy
MATCH p = (s:Session)-[:SPAWNED*]->(a:Agent)
RETURN s.session_id, a.agent_id, a.agent_type, a.status

-- Tool latency by agent
MATCH (a:Agent)-[r:INVOKED]->(t:Tool)
WHERE r.duration_ms IS NOT NULL
RETURN a.agent_id, t.name, r.duration_ms
ORDER BY r.duration_ms DESC

-- Failed tool calls with context
MATCH (a:Agent)-[r:INVOKED {status: 'failed'}]->(t:Tool)
RETURN a.agent_id, a.agent_type, t.name, r.tool_input, r.start_ts
```

Schema sidebar in the Query Console shows all available labels, types, and properties.

### NL-to-Cypher accuracy?

Uses `claude-sonnet-4-6` with a schema-aware system prompt and six example pairs. Common questions (running agents, spawn trees, tool failures, latency) produce correct Cypher consistently. Complex multi-hop traversals may need manual correction — switch to Cypher mode for precise control.

## Extensibility

### Adding new event types?

Three changes when Claude Code adds new hook events:

1. **`hooks/hooks.json`** — add the event with HTTP and (optionally) command delivery
2. **`collector/graph.py`** — handler function in `_HANDLERS` dict for graph mutations, or a no-op lambda for DuckDB-only events
3. **`skills/observer-context/SKILL.md`** — update so Claude knows about it

`ledger.py` handles field extraction generically. Full payload JSON stored regardless.

### Adding a new dashboard view?

1. New route: `dashboard/src/routes/{view-name}/+page.svelte`
2. Sidebar nav item in `Sidebar.svelte`
3. `Cmd+N` keyboard shortcut in layout
4. Wire to SSE store, REST endpoint, or both

See [Contributing](contributing.md) for dev setup.
