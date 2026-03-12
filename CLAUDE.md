# CC Observer

Real-time execution graph monitoring for Claude Code. Captures lifecycle events via hooks, writes raw payloads to DuckDB, materializes a labeled property graph in LadybugDB, and serves a SvelteKit dashboard. The entire backend runs as a Docker Compose stack managed by plugin commands.

## Tech Stack

- **Collector**: Python / FastAPI
- **Event ledger**: DuckDB
- **Graph DB**: LadybugDB (`pip install real_ladybug`)
- **Dashboard**: SvelteKit
- **Infrastructure**: Docker Compose
- **Plugin integration**: Claude Code hooks (http primary, command fallback), MCP server (LadybugDB), NL→Cypher via Anthropic API

## Architecture

- Claude Code hooks POST events to `localhost:4001`
- Collector writes to DuckDB (immutable source of truth) and materializes graph in LadybugDB
- Dashboard consumes SSE from collector on port 4002, served on port 3000
- LadybugDB MCP server gives Claude direct Cypher execution
- `scripts/replay.py` rebuilds LadybugDB from DuckDB if needed

## Build Phases

1. Docker stack + hook plumbing (FastAPI collector, DuckDB, LadybugDB, dual hook delivery)
2. Graph materialization (per-event Cypher mutations, DDL, replay script)
3. Plugin shell (plugin.json, commands, skill, agent, .mcp.json)
4. NL→Cypher (Anthropic API, /api/ask endpoint, /oc:query command)
5. Dashboard (SvelteKit + nginx, SSE + REST wiring)

## DreamTeams Plugins

- **dt-core** — foundation (dev/dreamteam agents, GitHub, mermaid, skills)
- **dt-mcp** — this project builds MCP server integrations
- **dt-opensource** — open source project patterns
- **dt-data** — DuckDB, LadybugDB, event pipeline patterns
- **dt-nerdherd** — graph theory, Cypher, distributed systems depth

## Design Doc

Full architecture spec: `docs/ref/source-material/cc-observer-plan-v2.md`
