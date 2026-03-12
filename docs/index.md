---
title: CC Observer Documentation
description: Real-time execution graph monitoring for Claude Code — documentation home
---

# CC Observer

Real-time execution graph monitoring for Claude Code. Every lifecycle event captured, materialized into a live property graph, served on a dashboard. You see exactly what your agents are doing.

## Docs

- **[Vision](vision.md)** — Why this exists, who it's for, design principles
- **[Architecture](architecture.md)** — System design, event lifecycle, storage, Docker topology
- **[Technical Spec](technical-spec.md)** — Graph schema, DuckDB schema, API reference, hook events, NL-to-Cypher
- **[UX & Dashboard](ux.md)** — Six views, design system, interaction patterns
- **[FAQ](faq.md)** — Installation, performance, data, querying, extensibility
- **[Contributing](contributing.md)** — Dev setup, project structure, adding handlers and views

## Stack

| Component | Technology | Purpose |
|---|---|---|
| Collector | Python / FastAPI | Event ingestion, graph materialization, API + SSE |
| Event Ledger | DuckDB | Immutable source of truth for all hook events |
| Execution Graph | LadybugDB | Labeled property graph for topology queries |
| Dashboard | SvelteKit + Cytoscape.js | Real-time visualization across 6 views |
| Infrastructure | Docker Compose | Single-command deployment |
| Plugin | Claude Code hooks + commands | Automatic event capture and CLI management |
| NL Query | Anthropic API | Natural language to Cypher translation |

## Quickstart

```bash
git clone https://github.com/halcyondude/observable-claude.git
cd observable-claude
export ANTHROPIC_API_KEY=sk-ant-...
docker compose up -d
open http://localhost:3000
```

Full quickstart in the [README](https://github.com/halcyondude/observable-claude#readme).
