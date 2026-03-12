---
title: Contributing
description: Development setup, project structure, how to add event handlers and views, testing, and PR workflow
---

# Contributing

## Dev Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (collector tests)
- Node.js 20+ (dashboard dev)
- Claude Code with plugin support (E2E testing)

### Clone and Start

```bash
git clone https://github.com/halcyondude/observable-claude.git
cd observable-claude

export ANTHROPIC_API_KEY=sk-ant-...  # optional, only for NL queries
docker compose up -d

curl http://localhost:4001/health
# {"status": "ok", "events_total": 0, "uptime_seconds": ...}

open http://localhost:3000
```

### Local Collector Dev

Faster iteration without Docker rebuilds:

```bash
cd collector
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

DUCKDB_PATH=../data/duckdb/events.db LADYBUG_PATH=../data/ladybug \
    uvicorn collector:app --host 0.0.0.0 --port 8000 --reload
```

### Local Dashboard Dev

```bash
cd dashboard
npm install
npm run dev
# http://localhost:5173 with HMR
# Set PUBLIC_COLLECTOR_URL=http://localhost:4002 in .env
```

## Project Structure

```
cc-observer/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── hooks/
│   └── hooks.json               # 12 event types
├── commands/
│   ├── oc-setup.md              # /oc:setup
│   ├── oc-start.md              # /oc:start
│   ├── oc-stop.md               # /oc:stop
│   ├── oc-status.md             # /oc:status
│   └── oc-query.md              # /oc:query [question]
├── skills/
│   └── observer-context/
│       └── SKILL.md             # Graph schema + query patterns
├── agents/
│   └── observer-analyst.md      # Post-session analysis agent
├── collector/
│   ├── __init__.py
│   ├── collector.py             # FastAPI app
│   ├── ledger.py                # DuckDB ops
│   ├── graph.py                 # LadybugDB mutations + queries
│   ├── nl_query.py              # NL-to-Cypher
│   ├── Dockerfile
│   └── requirements.txt
├── dashboard/
│   ├── src/
│   │   ├── routes/              # SvelteKit pages
│   │   ├── lib/
│   │   │   ├── components/
│   │   │   ├── stores/          # session, events, connection
│   │   │   └── services/        # SSE client, API wrappers
│   │   └── app.css              # Design tokens
│   ├── Dockerfile               # Multi-stage: Node build -> nginx
│   ├── nginx.conf               # Proxy /api/*, /stream -> collector
│   └── package.json
├── scripts/
│   ├── setup.sh                 # docker compose up + health check
│   ├── teardown.sh              # docker compose down
│   ├── emit_event.py            # Command hook fallback
│   ├── replay.py                # Rebuild LadybugDB from DuckDB
│   └── smoke_test.sh            # E2E verification
├── data/                        # Gitignored
├── docker-compose.yml
├── .mcp.json                    # LadybugDB MCP server
└── README.md
```

## Adding a New Event Handler

When Claude Code introduces a new hook event type:

### 1. Hook Configuration

Add to `hooks/hooks.json`:

```json
"NewEventType": [
  {
    "hooks": [
      { "type": "http", "url": "http://localhost:4001/events" },
      { "type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/emit_event.py NewEventType" }
    ]
  }
]
```

Omit command fallback for events that shouldn't spawn subprocesses.

### 2. Graph Mutation

Handler in `collector/graph.py`:

```python
def _handle_new_event(conn: Connection, event: dict) -> None:
    some_id = _extract(event, "event.some_id", "some_id")
    conn.execute(
        "MATCH (a:Agent {agent_id: $aid}) SET a.some_property = $val",
        parameters={"aid": some_id, "val": "..."},
    )
```

Register in `_HANDLERS`:

```python
_HANDLERS = {
    # ...
    "NewEventType": _handle_new_event,
}
```

DuckDB-only (no graph mutation):

```python
"NewEventType": lambda conn, event: None,
```

### 3. Update the Skill

Add the event to `skills/observer-context/SKILL.md` so Claude knows about it.

No `ledger.py` changes needed — field extraction is generic, full payload JSON always stored.

## Adding a New Dashboard View

### 1. Create the Route

```bash
mkdir -p dashboard/src/routes/my-view
```

`+page.svelte`:

```svelte
<script lang="ts">
  import { events } from '$lib/stores/events';
  import { session } from '$lib/stores/session';
</script>

<div class="view-container">
  <!-- View content -->
</div>
```

### 2. Navigation

In `Sidebar.svelte`:

```svelte
<NavItem href="/my-view" icon={MyIcon} label="My View" shortcut="Cmd+7" />
```

### 3. Keyboard Shortcut

In `+layout.svelte`:

```typescript
case '7': goto('/my-view'); break;
```

### 4. Wire Data

- **Real-time:** Subscribe to events store (SSE-fed)
- **On-demand:** Fetch from REST via `$lib/services/api.ts`
- **Both:** Most views use SSE for live + REST for initial state

## Testing

### Collector

```bash
cd collector
python -m pytest tests/ -v
```

Key areas: `ledger.py` (write, query, sessions), `graph.py` (DDL, mutations, queries), `collector.py` (endpoint integration).

### Smoke Test

Full pipeline verification:

```bash
bash scripts/smoke_test.sh
```

Simulates a complete session (SessionStart through SessionEnd), verifies DuckDB writes, graph materialization, and SSE delivery.

### Dashboard

```bash
cd dashboard
npm run test        # Unit tests
npm run test:e2e    # Playwright E2E
```

## PR Workflow

1. Feature branch from `main`
2. Clear, descriptive commits
3. Run smoke test + relevant unit tests
4. PR with short title (<70 chars), description of what/why, test plan
5. Verify Docker stack starts clean: `docker compose build && docker compose up -d`

## Code Style

- **Python:** Follow existing collector patterns. Type hints. Docstrings on public functions.
- **TypeScript/Svelte:** SvelteKit conventions. TypeScript for all new code. CSS custom properties.
- **Cypher:** Parameterized queries (`$param`). MERGE for idempotent creates. MATCH + SET for updates.
- **Commits:** Type prefix: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
