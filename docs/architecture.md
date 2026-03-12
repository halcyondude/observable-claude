---
title: Architecture
description: System design, event lifecycle, storage strategy, Docker topology, and component interactions
---

# Architecture

## System Overview

CC Observer is a local observability stack for Claude Code. It captures lifecycle events via hooks, stores them in a dual-database architecture (DuckDB for analytics, LadybugDB for graph queries), and serves a real-time dashboard.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#0A9396', 'primaryBorderColor': '#0A9396', 'primaryTextColor': '#F4F8FB', 'lineColor': '#64748B', 'secondaryColor': '#1E293B', 'tertiaryColor': '#0D1B2A'}}}%%
flowchart TB
    subgraph HOST ["Host Machine"]
        direction TB
        CC["Claude Code<br/>Agent Runtime"]:::primary
        HOOKS["hooks.json<br/>12 event types"]:::config

        CC -->|fires| HOOKS
    end

    subgraph DOCKER ["Docker Compose Stack"]
        direction TB
        subgraph COLLECTOR ["Collector Service · FastAPI · Python 3.12"]
            direction LR
            INGEST["/events<br/>POST :4001"]:::endpoint
            SSE_EP["/stream<br/>GET :4002"]:::endpoint
            REST["/api/*<br/>GET/POST :4002"]:::endpoint
            NL["NL-to-Cypher<br/>Anthropic API"]:::module
            GRAPH_MOD["graph.py<br/>Materialization"]:::module
            LEDGER_MOD["ledger.py<br/>Event Writer"]:::module

            INGEST --> LEDGER_MOD
            INGEST --> GRAPH_MOD
            INGEST --> SSE_EP
            REST --> NL
        end

        subgraph STORAGE ["Persistent Storage · Docker Volumes"]
            direction LR
            DUCK[("DuckDB<br/>Event Ledger")]:::storage
            LADY[("LadybugDB<br/>Execution Graph")]:::storage
        end

        subgraph DASH_SVC ["Dashboard Service · SvelteKit + nginx"]
            direction LR
            NGINX["nginx<br/>Reverse Proxy :3000"]:::endpoint
            SVELTE["SvelteKit<br/>Cytoscape.js"]:::ui
            NGINX --> SVELTE
        end

        LEDGER_MOD --> DUCK
        GRAPH_MOD --> LADY
        REST -.->|reads| DUCK
        REST -.->|reads| LADY
        SSE_EP -->|push| NGINX
        REST -->|fetch| NGINX
    end

    subgraph MCP ["MCP Server"]
        LADY_MCP["mcp-server-ladybug<br/>Direct Cypher Access"]:::module
    end

    HOOKS -->|"HTTP POST localhost:4001"| INGEST
    HOOKS -.->|"command fallback emit_event.py"| INGEST
    LADY -.-> LADY_MCP
    LADY_MCP -.->|"mcp__ladybug-observer__query"| CC

    classDef primary fill:#0A9396,stroke:#0A9396,color:#F4F8FB,stroke-width:2px
    classDef endpoint fill:#1E293B,stroke:#0A9396,color:#F4F8FB
    classDef module fill:#2D3E50,stroke:#64748B,color:#F4F8FB
    classDef storage fill:#1E293B,stroke:#94D2BD,color:#F4F8FB,stroke-width:2px
    classDef config fill:#1E293B,stroke:#EE9B00,color:#F4F8FB
    classDef ui fill:#1E293B,stroke:#EE9B00,color:#F4F8FB

    style HOST fill:#0D1B2A,stroke:#1E3A4A,color:#F4F8FB
    style DOCKER fill:#0D1B2A,stroke:#1E3A4A,color:#F4F8FB
    style COLLECTOR fill:#0D1B2A,stroke:#0A9396,color:#F4F8FB
    style STORAGE fill:#0D1B2A,stroke:#94D2BD,color:#F4F8FB
    style DASH_SVC fill:#0D1B2A,stroke:#EE9B00,color:#F4F8FB
    style MCP fill:#0D1B2A,stroke:#64748B,color:#F4F8FB
```

## Event Lifecycle

Every event goes through a deterministic pipeline: hook capture, HTTP delivery, DuckDB write (always), graph materialization (best-effort), SSE broadcast.

```mermaid
%%{init: {'theme': 'dark'}}%%
flowchart LR
    subgraph CAPTURE ["1 · Capture"]
        HOOK_FIRE["Claude Code<br/>fires hook"]:::step
        HTTP_POST["HTTP POST<br/>localhost:4001/events"]:::step
        CMD_FALL["Command Fallback<br/>emit_event.py"]:::fallback

        HOOK_FIRE --> HTTP_POST
        HOOK_FIRE -.->|if HTTP fails| CMD_FALL
        CMD_FALL -.->|"retry POST or write JSONL"| HTTP_POST
    end

    subgraph INGEST ["2 · Ingest"]
        PARSE["Parse Payload<br/>extract fields"]:::step
        WRITE_DUCK["write_event()<br/>DuckDB INSERT"]:::step
        GEN_ID["Generate<br/>event_id UUID"]:::step

        PARSE --> GEN_ID --> WRITE_DUCK
    end

    subgraph MATERIALIZE ["3 · Materialize"]
        ROUTE["Route by<br/>event_type"]:::step
        CYPHER["Execute Cypher<br/>mutation"]:::step
        SKIP["Skip<br/>DuckDB-only events"]:::fallback

        ROUTE -->|graph event| CYPHER
        ROUTE -.->|"Notification / PermissionRequest / PreCompact"| SKIP
    end

    subgraph BROADCAST ["4 · Broadcast"]
        QUEUE["Push to all<br/>SSE client queues"]:::step
        SSE_OUT["SSE frame<br/>event: type, data: JSON"]:::step

        QUEUE --> SSE_OUT
    end

    HTTP_POST --> PARSE
    WRITE_DUCK --> ROUTE
    WRITE_DUCK --> QUEUE

    classDef step fill:#1E293B,stroke:#0A9396,color:#F4F8FB
    classDef fallback fill:#1E293B,stroke:#CA6702,color:#F4F8FB,stroke-dasharray: 5 5

    style CAPTURE fill:#0D1B2A,stroke:#64748B,color:#F4F8FB
    style INGEST fill:#0D1B2A,stroke:#64748B,color:#F4F8FB
    style MATERIALIZE fill:#0D1B2A,stroke:#64748B,color:#F4F8FB
    style BROADCAST fill:#0D1B2A,stroke:#64748B,color:#F4F8FB
```

## Complete Event Journey

This sequence diagram traces a single session from start to completion, showing how each event flows through the system.

```mermaid
%%{init: {'theme': 'dark', 'sequence': {'mirrorActors': false}}}%%
sequenceDiagram
    participant CC as Claude Code
    participant COL as Collector
    participant DUCK as DuckDB
    participant LADY as LadybugDB
    participant SSE as SSE Stream
    participant DASH as Dashboard

    rect rgba(10, 147, 150, 0.1)
        Note over CC,DASH: Session Lifecycle
        CC->>COL: POST /events {SessionStart}
        COL->>DUCK: INSERT event row
        COL->>LADY: MERGE Session node
        COL->>SSE: broadcast SessionStart
        SSE->>DASH: render session in top bar
    end

    rect rgba(10, 147, 150, 0.1)
        Note over CC,DASH: Agent Spawning
        CC->>COL: POST /events {SubagentStart, agent_type: "planner"}
        COL->>DUCK: INSERT event row
        COL->>LADY: MERGE Agent node + CREATE SPAWNED edge
        COL->>SSE: broadcast SubagentStart
        SSE->>DASH: animate new node into spawn tree
    end

    rect rgba(238, 155, 0, 0.1)
        Note over CC,DASH: Tool Invocation (success)
        CC->>COL: POST /events {PreToolUse, tool: "Read"}
        COL->>DUCK: INSERT event row
        COL->>LADY: MERGE Tool node + CREATE INVOKED edge (pending)
        COL->>SSE: broadcast PreToolUse
        SSE->>DASH: show PRE row in Tool Feed

        CC->>COL: POST /events {PostToolUse, tool: "Read", duration: 45ms}
        COL->>DUCK: INSERT event row
        COL->>LADY: SET INVOKED.status=success, duration_ms=45
        COL->>SSE: broadcast PostToolUse
        SSE->>DASH: show POST row + duration in Tool Feed
    end

    rect rgba(202, 103, 2, 0.1)
        Note over CC,DASH: Tool Invocation (failure)
        CC->>COL: POST /events {PreToolUse, tool: "Write"}
        COL->>DUCK: INSERT event row
        COL->>LADY: CREATE INVOKED edge (pending)
        CC->>COL: POST /events {PostToolUseFailure, tool: "Write"}
        COL->>DUCK: INSERT event row
        COL->>LADY: SET INVOKED.status=failed
        COL->>SSE: broadcast PostToolUseFailure
        SSE->>DASH: flash coral in spawn tree + FAIL row in feed
    end

    rect rgba(10, 147, 150, 0.1)
        Note over CC,DASH: Session Complete
        CC->>COL: POST /events {SubagentStop}
        COL->>DUCK: INSERT event row
        COL->>LADY: SET Agent.end_ts, status=complete
        CC->>COL: POST /events {SessionEnd}
        COL->>DUCK: INSERT event row
        COL->>LADY: SET Session.end_ts
        COL->>SSE: broadcast SessionEnd
        SSE->>DASH: fade agents to gray, session archived
    end
```

## Storage Strategy

CC Observer uses two databases because they solve fundamentally different problems.

| Dimension | DuckDB | LadybugDB |
|---|---|---|
| **Data model** | Flat event rows | Labeled property graph |
| **Primary use** | Analytics, aggregation, full-text search | Topology, traversal, relationships |
| **Mutability** | Append-only (immutable ledger) | Live mutations per event |
| **Recovery** | Source of truth | Rebuilt from DuckDB via `replay.py` |
| **Query language** | SQL | Cypher |
| **Best for** | "What happened at 14:03?" "p95 latency?" | "Who spawned whom?" "Full spawn tree?" |
| **Size** | Grows with event count | Grows with session topology |

**Key design decision:** DuckDB is the immutable source of truth. LadybugDB is a materialized view of the graph structure. If LadybugDB gets corrupted, `scripts/replay.py` rebuilds it by replaying all events from DuckDB in order.

## Hook Delivery

Events reach the collector through dual delivery: HTTP primary with a command fallback for resilience.

```mermaid
%%{init: {'theme': 'dark'}}%%
flowchart TD
    EVENT["Claude Code<br/>fires event"]:::primary

    EVENT --> HTTP{"HTTP POST<br/>localhost:4001/events"}

    HTTP -->|"200 OK"| DONE["Event ingested"]:::success
    HTTP -->|"Connection refused or timeout"| CMD["Command fallback<br/>emit_event.py"]:::fallback

    CMD --> JSONL["Write to<br/>data/fallback.jsonl"]:::step
    CMD --> RETRY{"Retry HTTP POST<br/>1s timeout"}

    RETRY -->|"200 OK"| DONE
    RETRY -->|"Still down"| SAVED["Event saved in JSONL<br/>for later replay"]:::warn

    NOTE1["PermissionRequest<br/>Notification<br/>PreCompact"]:::note --> HTTP_ONLY["HTTP only<br/>no command fallback"]:::step
    HTTP_ONLY --> HTTP

    NOTE2["These events are http-only because<br/>spawning a subprocess during<br/>permission dialogs would block<br/>Claude Code visibly"]:::note

    classDef primary fill:#0A9396,stroke:#0A9396,color:#F4F8FB,stroke-width:2px
    classDef success fill:#1E293B,stroke:#94D2BD,color:#F4F8FB
    classDef step fill:#1E293B,stroke:#0A9396,color:#F4F8FB
    classDef fallback fill:#1E293B,stroke:#EE9B00,color:#F4F8FB
    classDef warn fill:#1E293B,stroke:#CA6702,color:#F4F8FB
    classDef note fill:#2D3E50,stroke:#64748B,color:#64748B,stroke-dasharray: 5 5
```

## Docker Compose Topology

The stack runs two services with shared volumes for persistent storage.

| Service | Image | Ports | Purpose |
|---|---|---|---|
| `collector` | `./collector` (Python 3.12) | `4001:8000`, `4002:8000` | Event ingestion, graph materialization, REST + SSE API |
| `dashboard` | `./dashboard` (SvelteKit + nginx) | `3000:80` | Static SvelteKit build served by nginx, proxies API to collector |

Both ports 4001 and 4002 map to the same internal port 8000 in the collector container. This is a single-process FastAPI app — the port split is for clarity (4001 = hooks, 4002 = dashboard API).

**Volume mounts:**

| Host Path | Container Path | Contents |
|---|---|---|
| `./data/duckdb/` | `/data/duckdb/` | `events.db` — DuckDB file |
| `./data/ladybug/` | `/data/ladybug/` | LadybugDB data directory |

Data persists across container restarts and survives `docker compose down`. Only `docker compose down -v` removes volumes.

## Port Map

| Port | Service | Protocol | Purpose |
|---|---|---|---|
| `3000` | Dashboard | HTTP | SvelteKit UI |
| `4001` | Collector | HTTP | Hook event ingestion (`POST /events`) |
| `4002` | Collector | HTTP + SSE | REST API (`/api/*`) and SSE stream (`/stream`) |

All ports are localhost-only. No auth required — this is a single-user local tool.
