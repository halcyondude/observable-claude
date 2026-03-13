---
name: observer-context
description: Context about the CC Observer execution graph monitoring system
autoload_triggers:
  - observer
  - running agents
  - execution graph
  - tool latency
  - spawn tree
  - session history
  - what claude is doing
---

# CC Observer — Execution Graph Context

## System Overview
CC Observer monitors Claude Code agent execution in real time. It captures lifecycle events via hooks, stores them in DuckDB (raw events) and LadybugDB (execution graph).

## Graph Schema

### Node Tables
- **Session**: session_id (PK), cwd, start_ts, end_ts
- **Agent**: agent_id (PK), agent_type, session_id, start_ts, end_ts, status (running|complete|failed)
- **Skill**: name (PK), path
- **Tool**: name (PK) — e.g., Bash, Write, Read, Edit, mcp__*

### Relationship Tables
- **SPAWNED**: Session->Agent or Agent->Agent. Properties: prompt, depth, spawned_at
- **LOADED**: Agent->Skill. Properties: loaded_at
- **INVOKED**: Agent->Tool. Properties: tool_use_id, tool_input, start_ts, end_ts, duration_ms, status (pending|success|failed), tool_response

## When to Query What

### Use LadybugDB (graph/Cypher) for:
- Which agents are running right now
- Full spawn tree: who spawned whom
- Variable-depth path traversal
- Tool call sequences per agent
- Cross-session skill usage patterns

### Use DuckDB (SQL) for:
- Raw event payloads (full JSON)
- Time-range scans: what happened at 14:03?
- Full-text search on prompts
- Aggregations: tool latency stats, event rates
- Replay: ordered events for graph reconstruction

## Common Cypher Patterns

### Find running agents
```cypher
MATCH (a:Agent {status: 'running'})
RETURN a.agent_id, a.agent_type, a.start_ts
ORDER BY a.start_ts;
```

### Full spawn tree for a session
```cypher
MATCH p = (s:Session {session_id: $sid})-[:SPAWNED*]->(a:Agent)
RETURN p;
```

### Tool call latency by agent
```cypher
MATCH (a:Agent)-[r:INVOKED]->(t:Tool)
WHERE r.duration_ms IS NOT NULL
RETURN a.agent_id, t.name, avg(r.duration_ms) AS avg_ms
ORDER BY avg_ms DESC;
```

### Failed tool calls
```cypher
MATCH (a:Agent)-[r:INVOKED {status: 'failed'}]->(t:Tool)
RETURN a.agent_id, t.name, r.tool_input, r.start_ts;
```

## Correlation Model
- `tool_use_id` links PreToolUse -> PostToolUse events for span timing
- `session_id` + `agent_id` identifies an agent within a session
- SPAWNED edge depth property tracks spawn tree depth

## Collector API
- `POST http://localhost:4001/events` — hook ingestion
- `GET http://localhost:4001/health` — liveness + stats
- `GET http://localhost:4002/stream` — SSE event stream
- `GET http://localhost:4002/api/sessions` — all sessions
- `GET http://localhost:4002/api/sessions/active` — live sessions
- `GET http://localhost:4002/api/sessions/{id}/graph` — Cytoscape.js JSON
- `GET http://localhost:4002/api/sessions/{id}/timeline` — Gantt data
- `GET http://localhost:4002/api/events` — raw DuckDB events
- `POST http://localhost:4002/api/ask` — NL->Cypher->result
- `POST http://localhost:4002/api/cypher` — raw Cypher execution

## Available Commands
- `/oc:setup` — configure API key and verify environment
- `/oc:start` — start the Docker stack
- `/oc:stop` — stop the Docker stack
- `/oc:status` — check observer health and activity
- `/oc:query [question]` — query the execution graph
- `/oc:visual-check [fix]` — autonomous visual QA of the dashboard (optionally auto-fix issues)
