---
title: Architecture
description: System design, event lifecycle, storage strategy, Docker topology, and component interactions
---

# Architecture

## System Overview

Local observability stack for Claude Code. Hooks capture lifecycle events, dual-database architecture stores them (DuckDB for analytics, LadybugDB for graph queries), real-time dashboard surfaces everything.

```mermaid
flowchart TB
    subgraph HOST ["Host"]
        CC["Claude Code"]
        HOOKS["hooks.json<br/>12 event types"]
        CC -->|fires| HOOKS
    end

    subgraph COLLECTOR ["Collector (FastAPI)"]
        INGEST["POST :4001<br/>/events"]
        SSE_EP["GET :4002<br/>/stream"]
        REST["GET/POST :4002<br/>/api/*"]
        NL["NL-to-Cypher"]
        GRAPH_MOD["graph.py"]
        LEDGER_MOD["ledger.py"]

        INGEST --> LEDGER_MOD
        INGEST --> GRAPH_MOD
        INGEST --> SSE_EP
        REST --> NL
    end

    subgraph STORAGE ["Storage (Docker Volumes)"]
        DUCK[("DuckDB<br/>Event Ledger")]
        LADY[("LadybugDB<br/>Exec Graph")]
    end

    subgraph DASH ["Dashboard (SvelteKit)"]
        NGINX["nginx :4242"]
        SVELTE["Cytoscape.js"]
        NGINX --> SVELTE
    end

    subgraph MCP ["MCP Server"]
        LADY_MCP["ladybug-observer<br/>Cypher access"]
    end

    HOOKS -->|"HTTP POST"| INGEST
    HOOKS -.->|"fallback: emit_event.py"| INGEST
    LEDGER_MOD --> DUCK
    GRAPH_MOD --> LADY
    REST -.->|reads| DUCK
    REST -.->|reads| LADY
    SSE_EP -->|push| NGINX
    REST -->|fetch| NGINX
    LADY -.-> LADY_MCP
    LADY_MCP -.->|MCP tool| CC
```

## Event Lifecycle

Deterministic pipeline: hook capture, HTTP delivery, DuckDB write (always), graph materialization (best-effort), SSE broadcast.

```mermaid
flowchart TB
    subgraph CAPTURE ["1. Capture"]
        HOOK["Hook fires"]
        HTTP["HTTP POST<br/>:4001/events"]
        CMD["Fallback<br/>emit_event.py"]

        HOOK --> HTTP
        HOOK -.->|if HTTP fails| CMD
        CMD -.->|retry or JSONL| HTTP
    end

    subgraph INGEST ["2. Ingest"]
        PARSE["Parse payload"]
        GEN_ID["Generate UUID"]
        WRITE_DUCK["DuckDB INSERT"]

        PARSE --> GEN_ID --> WRITE_DUCK
    end

    subgraph MATERIALIZE ["3. Materialize"]
        ROUTE["Route by type"]
        CYPHER["Cypher mutation"]
        SKIP["Skip (DuckDB-only)"]

        ROUTE -->|graph event| CYPHER
        ROUTE -.->|no-op events| SKIP
    end

    subgraph BROADCAST ["4. Broadcast"]
        QUEUE["SSE queues"]
        SSE_OUT["SSE frame"]
        QUEUE --> SSE_OUT
    end

    HTTP --> PARSE
    WRITE_DUCK --> ROUTE
    WRITE_DUCK --> QUEUE
```

## Complete Event Journey

Single session from start to completion — each event flowing through the system.

```mermaid
sequenceDiagram
    participant CC as Claude Code
    participant COL as Collector
    participant DUCK as DuckDB
    participant LADY as LadybugDB
    participant SSE as SSE Stream
    participant DASH as Dashboard

    rect rgba(10, 147, 150, 0.1)
        Note over CC,DASH: Session Lifecycle
        CC->>COL: POST {SessionStart}
        COL->>DUCK: INSERT event
        COL->>LADY: MERGE Session
        COL->>SSE: broadcast
        SSE->>DASH: render session
    end

    rect rgba(10, 147, 150, 0.1)
        Note over CC,DASH: Agent Spawning
        CC->>COL: POST {SubagentStart}
        COL->>DUCK: INSERT event
        COL->>LADY: MERGE Agent + SPAWNED edge
        COL->>SSE: broadcast
        SSE->>DASH: animate spawn tree
    end

    rect rgba(238, 155, 0, 0.1)
        Note over CC,DASH: Tool Use (success)
        CC->>COL: POST {PreToolUse, Read}
        COL->>DUCK: INSERT event
        COL->>LADY: MERGE Tool + INVOKED (pending)
        SSE->>DASH: show PRE row

        CC->>COL: POST {PostToolUse, 45ms}
        COL->>DUCK: INSERT event
        COL->>LADY: SET status=success
        SSE->>DASH: show POST + duration
    end

    rect rgba(202, 103, 2, 0.1)
        Note over CC,DASH: Tool Use (failure)
        CC->>COL: POST {PreToolUse, Write}
        COL->>LADY: INVOKED (pending)
        CC->>COL: POST {PostToolUseFailure}
        COL->>LADY: SET status=failed
        SSE->>DASH: flash failure
    end

    rect rgba(10, 147, 150, 0.1)
        Note over CC,DASH: Session Complete
        CC->>COL: POST {SubagentStop}
        COL->>LADY: SET Agent.end_ts
        CC->>COL: POST {SessionEnd}
        COL->>LADY: SET Session.end_ts
        SSE->>DASH: archive session
    end
```

## Storage Strategy

Two databases because they solve fundamentally different problems.

| Dimension | DuckDB | LadybugDB |
|---|---|---|
| **Data model** | Flat event rows | Labeled property graph |
| **Primary use** | Analytics, aggregation, full-text search | Topology, traversal, relationships |
| **Mutability** | Append-only (immutable ledger) | Live mutations per event |
| **Recovery** | Source of truth | Rebuilt from DuckDB via `replay.py` |
| **Query language** | SQL | Cypher |
| **Best for** | "What happened at 14:03?" | "Who spawned whom?" |
| **Size** | Grows with event count | Grows with session topology |

DuckDB is the immutable source of truth. LadybugDB is a materialized view. If LadybugDB gets corrupted, `scripts/replay.py` rebuilds it by replaying all events from DuckDB in order.

## Hook Delivery

Dual delivery: HTTP primary, command fallback for resilience.

```mermaid
flowchart TB
    EVENT["Hook fires"]

    EVENT --> HTTP{"HTTP POST<br/>:4001/events"}

    HTTP -->|200 OK| DONE["Ingested"]
    HTTP -->|fail| CMD["emit_event.py"]

    CMD --> JSONL["Write fallback.jsonl"]
    CMD --> RETRY{"Retry POST<br/>1s timeout"}

    RETRY -->|200 OK| DONE
    RETRY -->|still down| SAVED["Saved in JSONL<br/>for later replay"]

    NOTE["PermissionRequest<br/>Notification<br/>PreCompact"] --> HTTP_ONLY["HTTP only<br/>no fallback"]
    HTTP_ONLY --> HTTP
```

Three events skip the command fallback — spawning a subprocess during permission dialogs would block Claude Code.

## Docker Compose Topology

Two services, shared volumes.

```mermaid
flowchart TB
    subgraph COMPOSE ["docker compose"]
        subgraph COL ["collector · Python 3.12"]
            FA["FastAPI :8000"]
        end

        subgraph DASH ["dashboard · SvelteKit"]
            NG["nginx :80"]
        end

        subgraph VOLS ["volumes"]
            D[("duckdb/")]
            L[("ladybug/")]
        end

        FA --> D
        FA --> L
        NG -->|"/api/*, /stream"| FA
    end

    H4001["Host :4001<br/>hooks"] --> FA
    H4002["Host :4002<br/>API + SSE"] --> FA
    H4242["Host :4242<br/>dashboard"] --> NG
    DASH -->|depends_on healthy| COL
```

| Service | Image | Ports | Purpose |
|---|---|---|---|
| `collector` | `./collector` (Python 3.12) | `4001:8000`, `4002:8000` | Event ingestion, graph materialization, REST + SSE API |
| `dashboard` | `./dashboard` (SvelteKit + nginx) | `4242:80` | Static SvelteKit build served by nginx, proxies API to collector |

Ports 4001 and 4002 both map to internal port 8000. Single-process FastAPI app — the port split is for clarity (4001 = hooks, 4002 = dashboard API).

**Volumes:**

| Host Path | Container Path | Contents |
|---|---|---|
| `./data/duckdb/` | `/data/duckdb/` | `events.db` |
| `./data/ladybug/` | `/data/ladybug/` | LadybugDB data directory |

Data persists across container restarts and `docker compose down`. Only `docker compose down -v` removes volumes.

## Port Map

| Port | Service | Protocol | Purpose |
|---|---|---|---|
| `4242` | Dashboard | HTTP | SvelteKit UI |
| `4001` | Collector | HTTP | Hook ingestion (`POST /events`) |
| `4002` | Collector | HTTP + SSE | REST API (`/api/*`) + SSE (`/stream`) |

All localhost-only. No auth — single-user local tool.
