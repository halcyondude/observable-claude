---
title: CC Observer Documentation
description: Real-time execution graph monitoring for Claude Code — documentation home
---

# CC Observer Documentation

Real-time execution graph monitoring for Claude Code. Captures every lifecycle event, builds a live property graph, and serves a dashboard for understanding what your agents are doing.

## Quick Navigation

- **[Vision](vision.md)** — The problem we're solving, who this is for, and the design principles behind CC Observer
- **[Architecture](architecture.md)** — System design, event lifecycle, storage strategy, Docker topology
- **[Technical Specification](technical-spec.md)** — Graph schema, DuckDB schema, full API reference, hook event catalog, NL-to-Cypher pipeline
- **[UX & Dashboard Guide](ux.md)** — Six dashboard views, design system, interaction patterns, responsive behavior
- **[FAQ](faq.md)** — Answers to common questions about installation, performance, data storage, and extensibility
- **[Contributing](contributing.md)** — Development setup, project structure, how to add event handlers and views

## At a Glance

| Component | Technology | Purpose |
|---|---|---|
| Collector | Python / FastAPI | Event ingestion, graph materialization, API + SSE |
| Event Ledger | DuckDB | Immutable source of truth for all hook events |
| Execution Graph | LadybugDB (Kuzu fork) | Labeled property graph for topology queries |
| Dashboard | SvelteKit + Cytoscape.js | Real-time visualization across 6 views |
| Infrastructure | Docker Compose | Single-command deployment of the full stack |
| Plugin | Claude Code hooks + commands | Automatic event capture and CLI management |
| NL Query | Anthropic API | Natural language to Cypher translation |

## Getting Started

```bash
git clone https://github.com/halcyondude/observable-claude.git
cd observable-claude
export ANTHROPIC_API_KEY=sk-ant-...
docker compose up -d
open http://localhost:3000
```

See the [main README](https://github.com/halcyondude/observable-claude#readme) for the full quickstart.
