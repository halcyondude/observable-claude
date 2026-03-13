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
- Dashboard consumes SSE from collector on port 4002, served on port 4242
- LadybugDB MCP server gives Claude direct Cypher execution
- `scripts/replay.py` rebuilds LadybugDB from DuckDB if needed

## v1 Features (implemented, branch feat/19-integration)

- **Agent Conversations** — prompt capture, message graph, conversation panel, full-text search, response inference
- **Session Save/Replay** — bookmark/star sessions, .ccobs export/import, event replay with playback controls
- **Galaxy View** — multi-session overview with temporal swim lanes, uPlot time brush, workspace grouping by cwd, git branch detection
- **Tool Call Visualization** — 5 tool families (File/Exec/Agent/MCP/Meta), pip rings on spawn tree, expandable timeline rows, cross-view navigation
- **UI Testing** (in progress) — Playwright MCP, E2E tests, Histoire component stories, visual regression

## DreamTeams Plugins

- **dt-core** — foundation (dev/dreamteam agents, GitHub, mermaid, skills)
- **dt-mcp** — this project builds MCP server integrations
- **dt-opensource** — open source project patterns
- **dt-data** — DuckDB, LadybugDB, event pipeline patterns
- **dt-nerdherd** — graph theory, Cypher, distributed systems depth

## Design Doc

Full architecture spec: `docs/ref/source-material/cc-observer-plan-v2.md`
