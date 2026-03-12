# Agent Conversations — Full Prompt & Response Capture

> Feature plan for recording, storing, and surfacing the complete prompt/response lifecycle of Claude Code agents.

---

## Problem Statement

CC Observer captures the structural execution graph — which agents spawned, which tools they called, how long things took. But it's blind to the *content* of agent execution. We know Agent X was spawned by Agent Y and called Bash 14 times, but we can't see:

- What prompt Agent Y sent to Agent X
- What Agent X produced as its final output
- The conversation turns within Agent X's execution (the back-and-forth between user messages, assistant responses, and tool results)
- Why an agent failed — was the prompt ambiguous? Did it misunderstand the task?

This is the difference between seeing a call graph and reading the actual code. The structural view answers "what happened." The conversation view answers "why."

For debugging orchestrated multi-agent workflows (SuperMatt planning, then dispatching specialists), the prompt/response data is often the first thing you need and the one thing we don't have.

---

## What Data Is Available Today

### SubagentStart hook payload

Contains a `prompt` field — the text passed to the Agent tool when spawning a subagent. This is already stored as a property on the `SPAWNED` edge in LadybugDB. However:

- It may be truncated or partial in some cases
- It captures only the initial prompt, not follow-up conversation turns
- The prompt property on SPAWNED edges isn't surfaced prominently in the dashboard

### SubagentStop hook payload

Contains `agent_id` and status but **no response/output field**. This is the critical gap — Claude Code hooks don't currently expose what an agent produced.

### UserPromptSubmit hook payload

Contains the user's prompt text for the session-level agent. Currently stored as an edge property on SPAWNED. Same truncation concerns.

### Stop hook payload

Fires when an agent stops. Contains status but no output.

### What we don't get from hooks

- **Agent output/response text**: Not in any current hook payload. This is the biggest gap.
- **Intermediate conversation turns**: The back-and-forth within an agent's execution isn't exposed as discrete events.
- **Tool result text**: PostToolUse has `tool_response` but it can be massive (full file contents, command output). We store it in DuckDB's payload JSON but don't surface it well.

---

## Proposed Solution

### Strategy: Capture what we can, design for what's coming

Claude Code's hook system is actively evolving. Rather than waiting for perfect hook coverage, we build in three layers:

1. **Capture prompts now** — SubagentStart already gives us spawn prompts. Store them properly, surface them well.
2. **Infer responses from tool activity** — An agent's "output" is often the final tool call it makes (a Write, a Bash echo, etc.). We can reconstruct approximate output from the tool trace.
3. **Design the schema for full conversations** — When Claude Code adds response/conversation hooks (or we find a way to capture them), the storage and UI are already ready.

### Architecture Changes

#### New Graph Node: Message

```cypher
CREATE NODE TABLE Message (
  message_id STRING,
  agent_id STRING,
  session_id STRING,
  role STRING,         -- 'user' | 'assistant' | 'system'
  sequence INT64,      -- ordering within conversation
  timestamp TIMESTAMP,
  content_hash STRING, -- SHA-256 of content, for dedup
  content_preview STRING, -- first 500 chars
  PRIMARY KEY (message_id)
);

CREATE REL TABLE HAS_MESSAGE (
  FROM Agent TO Message,
  sequence INT64
);

CREATE REL TABLE NEXT (
  FROM Message TO Message
);
```

**Why a Message node instead of edge properties:** Messages are entities you want to traverse, search, and aggregate. "Show me all system prompts across sessions" or "find the response that preceded this failure" require node-level access. Edge properties can't be independently queried.

**Why content_preview on the node:** Full message content lives in DuckDB (see below). The graph node carries just enough text for Cypher queries and UI previews without blowing up LadybugDB's memory footprint.

#### Enhanced SPAWNED edge

```cypher
-- Add to existing SPAWNED relationship
ALTER REL TABLE SPAWNED ADD prompt_hash STRING;
ALTER REL TABLE SPAWNED ADD prompt_length INT64;
```

The full prompt text stays in DuckDB. The SPAWNED edge gets a hash for correlation and a length for quick size assessment.

#### DuckDB Schema Addition

```sql
CREATE TABLE messages (
  message_id    VARCHAR PRIMARY KEY,
  event_id      VARCHAR REFERENCES events(event_id),
  session_id    VARCHAR NOT NULL,
  agent_id      VARCHAR NOT NULL,
  role          VARCHAR NOT NULL,  -- 'user', 'assistant', 'system'
  sequence      INTEGER NOT NULL,
  timestamp     TIMESTAMPTZ NOT NULL,
  content       TEXT,              -- full message content, no truncation
  content_hash  VARCHAR,
  content_bytes INTEGER,
  metadata      JSON               -- tool_use_id, model, etc.
);

CREATE INDEX idx_msg_agent   ON messages(agent_id);
CREATE INDEX idx_msg_session ON messages(session_id);
CREATE INDEX idx_msg_role    ON messages(role);
CREATE INDEX idx_msg_hash    ON messages(content_hash);
```

**Why a separate table instead of more JSON in `events.payload`:** The events table is an append-only ledger. Messages need to be queried by agent, role, sequence, and searched by content. A normalized table with proper indexes is the right call. The `event_id` FK links back to the source event for provenance.

**Content column is TEXT, not JSON:** Prompts and responses are unstructured text. DuckDB's `regexp_matches` and `LIKE` handle full-text search on TEXT columns efficiently.

### Storage Budget

Rough sizing for a typical orchestrated session (1 planner + 5 specialist agents):

| Data | Per Agent | Per Session | Notes |
|---|---|---|---|
| Spawn prompt | 2-10 KB | 12-60 KB | Planner prompts are large (include full context) |
| Agent response | 1-20 KB | 6-120 KB | Varies wildly by task type |
| Intermediate turns | 5-50 KB | 30-300 KB | Tool results inflate this |
| **Total** | 8-80 KB | 48-480 KB | Manageable for DuckDB |

For a heavy day (20 sessions, 10 agents each): ~10-100 MB. DuckDB handles this without breaking a sweat. No need for external blob storage or compression at this scale.

If we later capture full tool results (file contents, command output), that changes the math. We'll add a `content_type` column and optional compression at that point.

### API Changes

#### New endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/agents/{id}/messages` | All messages for an agent, ordered by sequence |
| `GET` | `/api/sessions/{id}/messages` | All messages across all agents in a session |
| `GET` | `/api/messages/search` | Full-text search across message content |

#### Enhanced existing endpoints

| Endpoint | Change |
|---|---|
| `GET /api/sessions/{id}/graph` | Include Message nodes and HAS_MESSAGE edges in Cytoscape JSON |
| `GET /stream` (SSE) | New event type: `message` — broadcasts when a message is captured |

#### Search endpoint detail

```
GET /api/messages/search?q=<text>&session_id=<optional>&role=<optional>&agent_id=<optional>
```

Uses DuckDB `regexp_matches` or `LIKE` on `messages.content`. Returns message metadata + content_preview (first 500 chars). Full content available via `/api/agents/{id}/messages`.

### Dashboard UX Changes

#### 1. Conversation Panel (new component)

A slide-in panel (or tab within the existing detail panel) that shows the full conversation for a selected agent. Appears when clicking an agent node in Spawn Tree or a row in Timeline.

**Layout:**
- Chat-style message bubbles, role-colored
  - User/System messages: left-aligned, dark surface background
  - Assistant messages: right-aligned, teal-tinted background
- Messages ordered by sequence
- Tool calls shown inline as collapsed cards between messages
- Timestamps on each message
- "Copy" button per message and "Copy all" for the full conversation
- Scroll to bottom on load (most recent = most relevant)

**Interaction:**
- Searchable: Cmd+F within the panel filters/highlights matches
- Collapsible: Long messages (>500 chars) show preview with "expand" toggle
- Linkable: Each message has a permalink hash for sharing

#### 2. Spawn Tree Enhancement

- Agent nodes get a small "chat" icon badge when conversation data is available
- Selected Node Panel (existing 320px slide-in) gets a "Conversation" tab alongside the existing metadata tab
- SPAWNED edge tooltip shows full prompt text (scrollable), not just first 40 chars

#### 3. New Query Console Examples

Add conversation-aware query chips:

- "What prompt was given to the planner agent?"
- "Show me the response from the last failed agent"
- "Which agents received the longest prompts?"
- "Search messages for 'error' across all sessions"

#### 4. Session History Enhancement

- Session list items show message count alongside event count
- Session detail view includes conversation data for all agents

### Collector Changes

#### Event Processing

When processing `SubagentStart`:
1. Extract `prompt` field from payload
2. Write to `messages` table with `role='user'`, `sequence=0`
3. Create Message node in LadybugDB with content_preview
4. Create HAS_MESSAGE edge from Agent to Message
5. Update SPAWNED edge with `prompt_hash` and `prompt_length`
6. Broadcast `message` SSE event

When processing `SubagentStop`:
1. Check for output/response field (future hook enhancement)
2. If present: write to `messages` table with `role='assistant'`, `sequence=N`
3. Create Message node + HAS_MESSAGE edge
4. Broadcast `message` SSE event

When processing `UserPromptSubmit`:
1. Extract prompt text
2. Write to `messages` table for the session-level agent

#### Response Inference (interim)

Until Claude Code hooks expose agent responses directly, we can infer "what did the agent produce" by looking at the final tool calls before SubagentStop. This is imperfect but useful:

- If the last tool call is a Write: the file path and content hint at output
- If it's a Bash echo or similar: that's likely the response
- The agent's full tool trace already tells the story

This inference is clearly marked as "inferred" in the UI, not presented as the actual response.

### Privacy & Redaction

Prompts may contain sensitive data — API keys, file contents, user instructions. Options:

1. **No redaction by default** — CC Observer is a local-only tool. Data never leaves the machine. The DuckDB file is in a gitignored `data/` directory.
2. **Optional redaction config** — A `redaction.yaml` that specifies patterns to scrub (regex for API keys, email addresses, etc.) applied at write time.
3. **Retention policy** — Auto-purge messages older than N days. Configurable via environment variable.

Recommendation: Ship with option 1 (no redaction). Add option 2 as a fast-follow if users request it. Option 3 is good hygiene regardless.

---

## Phased Implementation

### Phase 1: Prompt Capture & Storage (foundation)

**Scope:** DuckDB `messages` table, collector writes prompts from SubagentStart and UserPromptSubmit, basic API endpoint.

- Create `messages` table in DuckDB
- Modify collector to extract and store prompts from SubagentStart, UserPromptSubmit
- Add `GET /api/agents/{id}/messages` endpoint
- Update `replay.py` to populate messages from historical events
- Unit tests for message extraction and storage

**Dependencies:** None — builds on existing collector.
**Complexity:** M

### Phase 2: Graph Schema & Materialization

**Scope:** Message nodes and HAS_MESSAGE edges in LadybugDB, enhanced SPAWNED edge properties, NL query schema update.

- Create Message node table and HAS_MESSAGE/NEXT relationship tables
- Modify `graph.py` to create Message nodes on prompt capture
- Update SPAWNED edge with prompt_hash and prompt_length
- Update NL query system prompt with new schema
- Update `replay.py` to materialize Message nodes
- Add conversation-aware example Cypher queries

**Dependencies:** Phase 1 (messages must exist in DuckDB first).
**Complexity:** M

### Phase 3: Dashboard Conversation Panel

**Scope:** New Conversation component in dashboard, Spawn Tree integration, SSE message events.

- Build Conversation panel component (chat-style message display)
- Add "Conversation" tab to Spawn Tree selected node panel
- Add `message` event type to SSE stream
- Wire panel to `/api/agents/{id}/messages` endpoint
- Add chat icon badge to agent nodes with conversation data
- Handle long content: preview/expand toggle, copy buttons

**Dependencies:** Phase 1 (API), Phase 2 (graph data for node badges).
**Complexity:** L

### Phase 4: Search & Query Integration

**Scope:** Full-text search endpoint, Query Console examples, Session History enhancements.

- Add `GET /api/messages/search` endpoint with DuckDB full-text search
- Add `GET /api/sessions/{id}/messages` endpoint
- Add conversation-aware query chips to Query Console
- Update Session History to show message counts
- Add message content to session detail view

**Dependencies:** Phases 1-3.
**Complexity:** M

### Phase 5: Response Capture (when available)

**Scope:** Capture agent responses when Claude Code hooks support it. Response inference as interim.

- Monitor Claude Code hook changelog for response/output fields
- Implement response capture from SubagentStop when available
- Build interim response inference from final tool calls
- Mark inferred responses distinctly in UI
- Add retention policy (env var for auto-purge age)

**Dependencies:** Phases 1-4 complete. External dependency on Claude Code hook evolution.
**Complexity:** M-L (uncertainty in hook timeline)

---

## Open Questions

1. **Claude Code hook roadmap**: Will SubagentStop gain a `response` or `output` field? This determines whether Phase 5 is "flip a switch" or "build an inference engine." Worth checking with the Claude Code team or hook documentation.

2. **Conversation turns within agents**: Agents have internal conversation loops (user message -> assistant response -> tool call -> tool result -> assistant response). Are these exposed as discrete events, or do we only see the tool-level events? This affects how complete our conversation view can be.

3. **Content size limits**: Should we cap message content at some threshold (e.g., 1 MB) and store a truncated version + hash? For 99% of cases the full content fits easily, but a pathological prompt with embedded file contents could be large.

4. **Message dedup**: If we replay from DuckDB, the same prompt appears in the `events.payload` column and the `messages.content` column. Acceptable redundancy for query flexibility, or should messages be extracted views over events?

5. **Graph visualization density**: Adding Message nodes to the Spawn Tree Cytoscape graph could make it noisy. Should messages only appear in the detail panel, not as nodes in the graph view? Probably yes — the graph should stay structural, conversations belong in the detail panel.

6. **SPAWNED edge prompt text**: The existing `prompt` property on SPAWNED edges stores full prompt text in LadybugDB. With the new Message node approach, should we deprecate the edge property and rely on the Message node instead? Migration path needed.
