---
title: Contributing
description: Development setup, project structure, how to add event handlers and views, testing, and PR workflow
---

# Contributing

## Development Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for running collector tests locally)
- Node.js 20+ (for dashboard development)
- Claude Code with plugin support (for end-to-end testing)

### Clone and Start

```bash
git clone https://github.com/halcyondude/observable-claude.git
cd observable-claude

# Start the full stack
export ANTHROPIC_API_KEY=sk-ant-...  # optional, only needed for NL queries
docker compose up -d

# Verify
curl http://localhost:4001/health
# → {"status": "ok", "events_total": 0, "uptime_seconds": ...}

open http://localhost:3000
```

### Local Collector Development

For faster iteration on the collector without rebuilding the Docker image:

```bash
cd collector
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run locally (uses ./data/ relative to project root)
DUCKDB_PATH=../data/duckdb/events.db KUZU_PATH=../data/kuzu \
    uvicorn collector:app --host 0.0.0.0 --port 8000 --reload
```

### Local Dashboard Development

```bash
cd dashboard
npm install
npm run dev
# Dashboard at http://localhost:5173 with HMR
# Set PUBLIC_COLLECTOR_URL=http://localhost:4002 in .env for API proxying
```

## Project Structure

```
cc-observer/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── hooks/
│   └── hooks.json               # Hook configuration (12 event types)
├── commands/
│   ├── start.md                 # /observer:start
│   ├── stop.md                  # /observer:stop
│   ├── status.md                # /observer:status
│   └── query.md                 # /observer:query [question]
├── skills/
│   └── observer-context/
│       └── SKILL.md             # Graph schema + query patterns for Claude
├── agents/
│   └── observer-analyst.md      # Post-session analysis agent
├── collector/
│   ├── __init__.py
│   ├── collector.py             # FastAPI app — endpoints, SSE, lifecycle
│   ├── ledger.py                # DuckDB operations — write, query, sessions
│   ├── graph.py                 # LadybugDB — DDL, mutations, graph queries
│   ├── nl_query.py              # NL→Cypher via Anthropic API
│   ├── Dockerfile
│   └── requirements.txt
├── dashboard/
│   ├── src/
│   │   ├── routes/              # SvelteKit pages (one per view)
│   │   ├── lib/
│   │   │   ├── components/      # Svelte components
│   │   │   ├── stores/          # Svelte stores (session, events, connection)
│   │   │   └── services/        # SSE client, API wrappers
│   │   └── app.css              # Design tokens as CSS custom properties
│   ├── Dockerfile               # Multi-stage: Node build → nginx serve
│   ├── nginx.conf               # Reverse proxy: /api/* and /stream → collector
│   └── package.json
├── scripts/
│   ├── setup.sh                 # docker compose up + health check
│   ├── teardown.sh              # docker compose down
│   ├── emit_event.py            # Command hook fallback (JSONL + HTTP retry)
│   ├── replay.py                # Rebuild LadybugDB from DuckDB
│   └── smoke_test.sh            # End-to-end verification
├── data/                        # Gitignored — DuckDB + LadybugDB data
├── docker-compose.yml
├── .mcp.json                    # Kuzu MCP server registration
└── README.md
```

## How to Add a New Event Handler

When Claude Code introduces a new hook event type:

### Step 1: Hook Configuration

Add the new event to `hooks/hooks.json`:

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

Omit the command fallback for events that should not spawn subprocesses (e.g., during permission dialogs).

### Step 2: Graph Mutation (if applicable)

Add a handler function in `collector/graph.py`:

```python
def _handle_new_event(conn: Connection, event: dict) -> None:
    # Extract fields using _extract() helper
    some_id = _extract(event, "event.some_id", "some_id")
    # Execute Cypher mutation
    conn.execute(
        "MATCH (a:Agent {agent_id: $aid}) SET a.some_property = $val",
        parameters={"aid": some_id, "val": "..."},
    )
```

Register in the `_HANDLERS` dict:

```python
_HANDLERS = {
    # ... existing handlers ...
    "NewEventType": _handle_new_event,
}
```

For DuckDB-only events (no graph mutation), add a no-op:

```python
"NewEventType": lambda conn, event: None,
```

### Step 3: Update the Skill

Add the new event to `skills/observer-context/SKILL.md` so Claude knows about it when answering graph queries.

No changes needed in `ledger.py` — the DuckDB writer extracts fields generically from the nested/flat payload structure and stores the complete JSON in the `payload` column.

## How to Add a New Dashboard View

### Step 1: Create the Route

```bash
mkdir -p dashboard/src/routes/my-view
```

Create `+page.svelte` with the view implementation:

```svelte
<script lang="ts">
  import { events } from '$lib/stores/events';
  import { session } from '$lib/stores/session';
  // View logic
</script>

<div class="view-container">
  <!-- View content -->
</div>
```

### Step 2: Add Navigation

In `dashboard/src/lib/components/Sidebar.svelte`, add the new nav item:

```svelte
<NavItem href="/my-view" icon={MyIcon} label="My View" shortcut="Cmd+7" />
```

### Step 3: Add Keyboard Shortcut

In `dashboard/src/routes/+layout.svelte`, add the shortcut handler:

```typescript
case '7': goto('/my-view'); break;
```

### Step 4: Wire Data

Connect to the appropriate data source:
- **Real-time data:** Subscribe to the events store (fed by SSE)
- **On-demand data:** Fetch from REST endpoints via `$lib/services/api.ts`
- **Both:** Most views use SSE for live updates and REST for initial state

## Testing

### Collector Tests

```bash
cd collector
python -m pytest tests/ -v
```

Key test areas:
- `ledger.py` — event writing, querying, session aggregation
- `graph.py` — DDL initialization, per-event Cypher mutations, graph queries
- `collector.py` — endpoint integration tests with test client

### Smoke Test

The end-to-end smoke test verifies the full event pipeline:

```bash
bash scripts/smoke_test.sh
```

This simulates a complete session (SessionStart through SessionEnd) and verifies events land in DuckDB, the graph materializes correctly, and the SSE stream delivers events.

### Dashboard Tests

```bash
cd dashboard
npm run test        # Unit tests
npm run test:e2e    # Playwright end-to-end (if configured)
```

## PR Workflow

1. Create a feature branch from `main`
2. Make your changes with clear, descriptive commits
3. Run the smoke test and any relevant unit tests
4. Open a PR with:
   - A short title (under 70 characters)
   - Description of what changed and why
   - Test plan (how to verify the change works)
5. Ensure the Docker stack starts cleanly with your changes: `docker compose build && docker compose up -d`

## Code Style

- **Python:** Follow existing patterns in the collector. Use type hints. Docstrings on public functions.
- **TypeScript/Svelte:** Follow SvelteKit conventions. Use TypeScript for all new code. CSS custom properties for theming.
- **Cypher:** Use parameterized queries (`$param` syntax). MERGE for idempotent creates. MATCH + SET for updates.
- **Commit messages:** Start with a type prefix: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
