# CC Observer — Dashboard UI Design Specification

> Version 0.1 · For Designer Handoff

| | |
|---|---|
| **Product** | CC Observer — Claude Code execution monitor |
| **Purpose** | Read-only, real-time dashboard for monitoring Claude Code agent execution |
| **Primary user** | Developer (solo) running Claude Code locally |
| **Views** | 6 panels: Spawn Tree, Gantt, Tool Feed, Analytics, Query Console, Session History |
| **Stack** | SvelteKit (TypeScript) · Cytoscape.js · Tailwind CSS · SSE stream |
| **Deployment** | Docker container, localhost:3000 |
| **Interactivity** | Read-only — observation only, no control actions |

---

## 1. Product Context

CC Observer is a local-only dashboard that gives developers real-time visibility into Claude Code agent execution. It runs as a companion tab or second-monitor window while the developer works in their terminal.

The system is entirely read-only. There are no actions, no buttons that cause side effects, no ability to pause or control Claude Code. The dashboard is a window, not a control panel.

### 1.1 User & Context

- Single developer, running Claude Code in a terminal
- Dashboard is open as a companion — either split screen or second monitor
- Developer is actively working; the dashboard is peripheral, not primary focus
- Sessions may run for minutes to hours; agents may number from 1 to 20+
- Developer wants to answer: what is happening, what just happened, why is this slow

### 1.2 Data Sources

- SSE stream at `http://localhost:4002/stream` — real-time event push
- `GET /api/sessions` — session list with metadata
- `GET /api/sessions/{id}/graph` — Cytoscape.js nodes+edges JSON
- `GET /api/sessions/{id}/timeline` — Gantt data
- `GET /api/events` — paginated raw event log
- `POST /api/ask` — NL→Cypher (returns `{cypher, result, explanation}`)
- `POST /api/cypher` — raw Cypher execution

### 1.3 Design Principles

- **Information density over decoration** — this is a developer tool, not a marketing page
- **Dark theme primary** — developer works in a terminal; bright dashboards cause eye strain
- **Live data is the hero** — real-time updates must be visually obvious without being distracting
- **Failure is prominent** — errors, slow calls, and failed agents must be immediately visible
- **No empty states that look broken** — a session with no agents yet should look intentional
- **Responsive to content width** — should work at 900px (split screen) and 1600px+ (full tab)

---

## 2. Information Architecture

### 2.1 Global Layout

The application is a single-page app with a persistent sidebar (or top tab bar at narrow widths) for view navigation. The active session is always shown in a persistent status bar at the top.

#### Persistent Top Bar

| | |
|---|---|
| **Left** | CC Observer wordmark + version |
| **Center** | Active session: `session_id` (truncated) · `cwd` · elapsed time (live counter) |
| **Right** | Connection status pill (Connected / Reconnecting / Disconnected) · Agent count badge |
| **Height** | 48px |
| **Behavior** | Always visible; does not scroll. Session switcher opens from session_id. |

#### Left Sidebar Navigation

| | |
|---|---|
| **Width** | 200px expanded · 56px collapsed (icon only) |
| **Items** | Spawn Tree · Timeline · Tool Feed · Analytics · Query · Sessions |
| **Active indicator** | Teal left border + background tint |
| **Collapse** | Toggle button at bottom. At <960px viewport, collapses to icon-only automatically. |
| **Badges** | Spawn Tree shows live agent count · Tool Feed shows unread event count |

### 2.2 View List

| View | Primary Question Answered | Data Source |
|---|---|---|
| 1. Spawn Tree | What agents are running and how are they related? | SSE + `/graph` |
| 2. Timeline (Gantt) | How long has each agent been running? | SSE + `/timeline` |
| 3. Tool Feed | What tool calls are happening right now? | SSE stream |
| 4. Analytics | What are the performance patterns? | DuckDB via `/events` |
| 5. Query Console | Custom Cypher or NL question | `/ask` + `/cypher` |
| 6. Session History | What happened in past sessions? | `/sessions` |

---

## 3. View Specifications

---

### View 1: Spawn Tree
*Live graph of agent hierarchy — who spawned whom, what each is doing*

#### Purpose

The primary live view. Shows the execution graph for the current session as a directed tree. Nodes are agents; edges are spawn relationships. Updates in real time as agents start and stop.

#### Layout

- Full-bleed Cytoscape.js canvas occupying the view area
- Floating control strip in top-right corner: zoom in / zoom out / fit / reset layout
- Floating legend in bottom-left: node color meanings
- Selected node panel slides in from right (320px wide) when a node is clicked

#### Node Design

| | |
|---|---|
| **Shape** | Rounded rectangle |
| **Label** | `agent_type` (line 1, bold) · `agent_id` truncated (line 2, muted) |
| **Running** | Teal fill · white text · subtle pulse animation on border |
| **Complete** | Dark gray fill · muted text · no animation |
| **Failed** | Coral/red fill · white text · static |
| **Session root** | Navy fill, slightly larger, no pulse |
| **Size** | Proportional to number of tool calls (min 80px, max 160px wide) |

#### Edge Design

| | |
|---|---|
| **Style** | Directed arrow, teal color |
| **Label** | Prompt text (first 40 chars, truncated), shown on hover only |
| **Thickness** | 1.5px — uniform, not data-encoded |
| **Layout algorithm** | Dagre (top-to-bottom hierarchy). Fallback: cola for dense graphs. |

#### Selected Node Panel (slide-in)

- `agent_id` (full, monospace)
- `agent_type`
- Status badge (running / complete / failed)
- Started: absolute time + relative ("2m 14s ago")
- Duration: live counter if running, final if stopped
- Spawned by: `agent_id` or "Session" with link
- Prompt: full text of spawn prompt, scrollable
- Tools invoked: count + list of tool names with call counts
- Skills loaded: list

#### Behavior

- Graph updates live via SSE — new nodes animate in from their parent
- Completed agents fade to gray in place (do not disappear)
- Failed agents flash coral briefly, then hold color
- Auto-layout re-runs on new node if graph is not manually panned
- If user has panned/zoomed, new nodes appear without re-layout until "Reset" is clicked

> **Designer note:** The live pulse on running nodes should be subtle — a 2s ease-in-out border opacity cycle, not a scale pulse. Scale pulses are distracting at peripheral vision.

---

### View 2: Timeline (Gantt)
*Horizontal bars showing agent execution duration over wall-clock time*

#### Purpose

Shows how long each agent ran and when, as horizontal bars on a shared time axis. Makes parallelism and bottlenecks immediately visible.

#### Layout

- Left column (200px): agent label (`agent_type` + truncated `agent_id`)
- Right area: scrollable Gantt canvas with shared time axis at top
- Each agent row is 32px tall with 4px gap
- Time axis auto-scales to session duration; snaps to sensible intervals (1s, 5s, 30s, 1m, 5m)
- Current time indicator: thin teal vertical line at right edge, moves live

#### Bar Design

| | |
|---|---|
| **Running bar** | Teal fill, right edge animated (grows as agent runs) |
| **Complete bar** | Dark gray fill, fixed width |
| **Failed bar** | Coral fill, fixed width, ✕ icon at right end |
| **Hover tooltip** | `agent_id` · start time · duration · status · prompt (first 60 chars) |
| **Indent** | Child agents indented 16px per depth level in the left label column |

#### Tool Call Markers

- Small tick marks on each agent bar showing tool call events
- Tick color: teal for success, coral for failure
- Hover on tick: `tool_name` · duration · input summary

> **Designer note:** Ticks should be 2px wide × 12px tall, centered on the bar. At high density they will overlap — that's acceptable and expected.

#### Behavior

- New agents append as new rows at the bottom
- View auto-scrolls to show newest agents unless user has manually scrolled
- Time axis always shows last N seconds/minutes to fill the viewport (auto-scale)
- Session selector at top-right: switch between active and past sessions

---

### View 3: Tool Feed
*Scrolling live log of tool call events*

#### Purpose

A chronological event log showing every `PreToolUse`, `PostToolUse`, and `PostToolUseFailure` in real time. The developer's primary way to see what Claude is actively doing right now.

#### Layout

- Full-width scrolling list, newest events at top (reverse chronological)
- Filter bar at top: filter by event type, tool name, `agent_id`, status
- Pause button (top right): freeze scroll to read without new events pushing content

#### Event Row Design

| | |
|---|---|
| **Row height** | 48px (single-line summary) · expands to show full payload on click |
| **Left accent** | 4px colored left border: teal (PreToolUse), green (success), coral (failure) |
| **Timestamp** | `HH:MM:SS.mmm` — monospace, muted, leftmost column (80px) |
| **Event type badge** | Pill: `PRE` / `POST` / `FAIL` — colored accordingly |
| **Tool name** | Bold, e.g. `Bash`, `Write`, `mcp__kuzu-observer__query` |
| **Agent** | `agent_type` in muted text |
| **Duration** | Right-aligned, shown on PostToolUse rows only — e.g. `142ms` |
| **Summary** | Key tool input field — for Bash: first 60 chars of command; for Write: file path; for mcp__*: tool name + first arg |

#### Expanded Row (click to expand)

- Full `tool_input` as formatted JSON (syntax highlighted, dark background)
- For PostToolUse: `tool_response` summary (truncated at 500 chars, "show more" link)
- `agent_id` (full) · `session_id` · `tool_use_id` (for correlation)

#### Filter Bar

- Event type: All / PreToolUse / PostToolUse / Failure (multi-select pills)
- Tool name: text input with autocomplete from seen tool names
- Status: All / Success / Failure
- Filters apply live without page reload

> **Designer note:** The Pause button should be prominent — a developer reading a long tool output will be frustrated if new events push it off screen. Consider auto-pausing when user scrolls up.

---

### View 4: Analytics
*Aggregated performance metrics from DuckDB*

#### Purpose

Answers performance questions: which tools are slow, which agents fail most, what is the event rate. Uses DuckDB analytic queries rather than the SSE stream.

#### Layout

- 2×2 grid of stat cards at top (responsive: 4-across at wide, 2×2 at medium, 1 column at narrow)
- Two charts below: tool latency distribution (horizontal bar), event rate over time (area chart)
- Table at bottom: per-tool aggregate stats
- Time range selector: Last 5m / 30m / 1h / Session / All time

#### Stat Cards

| | |
|---|---|
| **Card 1** | Total Events — count with delta vs previous period |
| **Card 2** | Active Agents — live count (green) + completed today |
| **Card 3** | Tool Success Rate — % with color coding (>95% green, <80% red) |
| **Card 4** | Median Tool Latency — p50 in ms, with p95 in smaller text below |

#### Tool Latency Chart

- Horizontal bar chart — one row per tool name
- Bar length = p50 latency; second segment = p95
- Color: teal for fast (<100ms), amber for medium (100–500ms), coral for slow (>500ms)
- Sorted by p95 descending (worst first)

#### Event Rate Chart

- Area chart: events per 10-second bucket over selected time range
- X axis: wall clock time. Y axis: event count.
- Stacked by event type (PreToolUse, PostToolUse, SubagentStart, etc.) with legend

#### Per-Tool Table

| Tool | Calls (success / fail) | Latency p50 / p95 |
|---|---|---|
| Bash | 142 / 3 | 88ms / 420ms |
| Write | 67 / 0 | 12ms / 45ms |
| mcp__kuzu-observer__query | 31 / 1 | 210ms / 890ms |

*Table above shows example data only.*

---

### View 5: Query Console
*Natural language and raw Cypher queries against LadybugDB*

#### Purpose

Allows ad-hoc questions about the execution graph. Accepts both natural language (converted to Cypher via the Anthropic API) and raw Cypher. Results display as a table or graph depending on return type.

#### Layout

- Top: mode toggle — "Natural Language" | "Cypher"
- Input area: multi-line text input (grows to ~6 lines)
- "Ask" button (right of input) — keyboard shortcut: `Cmd+Enter`
- Below input: last generated Cypher (always shown even in NL mode, collapsible)
- Results panel: table for tabular results, mini Cytoscape graph for graph results

#### Natural Language Mode

| | |
|---|---|
| **Input placeholder** | "Which agents are currently running?" or "Show me failed tool calls in the last 5 minutes" |
| **On submit** | `POST /api/ask` · show loading spinner · display result |
| **Generated Cypher** | Shown in collapsed code block below input, expand to see. Syntax highlighted. |
| **Explanation** | One-line plain-English explanation of what the Cypher does |
| **Error handling** | If Cypher fails: show error + offer to retry with clarification |

#### Cypher Mode

| | |
|---|---|
| **Input** | Code editor (Monaco or CodeMirror) with Cypher syntax highlighting |
| **On submit** | `POST /api/cypher` · execute directly |
| **Schema sidebar** | Collapsible panel showing all node labels, relationship types, and properties |

#### Results Panel

- Tabular results: data table with sortable columns, copy-to-CSV button
- Graph results (when query returns nodes/edges): mini Cytoscape.js canvas, same node styling as Spawn Tree
- Empty results: "No results" state — not an error
- Query history: last 20 queries accessible via dropdown, persisted in localStorage

#### Example Query Chips (pre-loaded in NL mode)

- "Which agents are currently running?"
- "Show me the spawn tree for this session"
- "What tool calls failed in the last 10 minutes?"
- "Which skills were loaded most often today?"
- "What was the slowest tool call this session?"

---

### View 6: Session History
*Browse and replay past sessions*

#### Purpose

List of all past and active sessions. Clicking a session loads its graph, timeline, and events into the other views. Enables post-mortem analysis of completed runs.

#### Layout

- Left panel (320px): session list, sorted newest first
- Right panel: session detail for selected session (same views as live, but from stored data)

#### Session List Item

| | |
|---|---|
| **Status indicator** | Green dot (active) or gray dot (completed) |
| **Primary text** | `cwd` — last path segment in bold, full path in smaller text below |
| **Metadata** | Start time · Duration · Agent count · Event count |
| **Active session** | Highlighted with teal left border, "LIVE" badge |

#### Session Detail

- When a past session is selected, all 5 other views switch to that session's data
- A banner at top indicates "Viewing archived session — `[session_id]` · `[date]`"
- Banner has "Return to live" button to switch back to active session
- Timeline and Spawn Tree show the final state (all agents complete)
- Tool Feed shows full event log, scrollable from bottom (oldest) to top (newest)

---

## 4. Design Tokens

### 4.1 Color Palette

| Token | Hex | Usage |
|---|---|---|
| `--color-primary` | `#0A9396` | Teal — running agents, active elements, links |
| `--color-bg` | `#0D1B2A` | Navy — app background, dark areas |
| `--color-surface` | `#1E293B` | Cards, panels, sidebars |
| `--color-surface-2` | `#2D3E50` | Inputs, code blocks, hover states |
| `--color-success` | `#94D2BD` | Mint — completed agents, success states |
| `--color-warning` | `#EE9B00` | Amber — medium latency, caution |
| `--color-error` | `#CA6702` | Coral — failed agents/tools, errors |
| `--color-text` | `#F4F8FB` | Near-white — primary text |
| `--color-text-muted` | `#64748B` | Gray — secondary labels, timestamps |
| `--color-border` | `#1E3A4A` | Subtle borders between panels |

### 4.2 Typography

| Element | Font / Size / Weight | Usage |
|---|---|---|
| Display | Inter 24px Bold | View titles, section headers |
| Label | Inter 14px Medium | Card labels, nav items, column headers |
| Body | Inter 13px Regular | Event descriptions, panel text |
| Caption | Inter 11px Regular | Timestamps, metadata, muted info |
| Code | JetBrains Mono 12px | Cypher queries, JSON payloads, IDs |
| Monospace data | JetBrains Mono 13px | `agent_id`, `tool_use_id`, `session_id` |

### 4.3 Spacing & Sizing

| Token | Value | Usage |
|---|---|---|
| `--space-1` | 4px | Tight gaps, inline padding |
| `--space-2` | 8px | Component internal padding |
| `--space-3` | 12px | Between related elements |
| `--space-4` | 16px | Standard panel padding |
| `--space-6` | 24px | Between sections |
| `--radius-sm` | 4px | Badges, small pills |
| `--radius-md` | 8px | Cards, panels |
| `--radius-lg` | 12px | Modals, large surfaces |
| Top bar height | 48px | Fixed |
| Sidebar width | 200px / 56px | Expanded / collapsed |
| Slide-in panel | 320px | Node detail, schema sidebar |

---

## 5. Component Specifications

### 5.1 Status Badge

| | |
|---|---|
| **Running** | Teal background · white text · 6px dot with pulse animation on left |
| **Complete** | Gray background · muted text · static dot |
| **Failed** | Coral background · white text · ✕ icon |
| **Connected** | Green dot, no text (used in top bar) |
| **Disconnected** | Red dot (used in top bar) · triggers reconnect attempt |
| **Size** | Height 20px · padding 4px 8px · font 11px medium |

### 5.2 Stat Card

| | |
|---|---|
| **Structure** | Label (top, 11px muted) · large value (center, 32px bold) · delta (bottom, 11px, colored) |
| **Width** | Flexible — fills grid cell |
| **Height** | 88px fixed |
| **Background** | `--color-surface` |
| **Border** | 1px `--color-border`, `--radius-md` |
| **Live update** | Value updates in place — no flash, no transition (too distracting at peripheral vision) |

### 5.3 Event Row

| | |
|---|---|
| **Collapsed height** | 48px |
| **Expanded height** | Auto — minimum 200px |
| **Left border** | 4px solid: teal (PreToolUse), green (PostToolUse), coral (Failure) |
| **Hover state** | Background lightens by one shade |
| **Click target** | Entire row — toggles expansion |
| **Expansion animation** | Height animates 150ms ease-out |
| **JSON highlighting** | Dark background: keys teal, strings amber, numbers mint |

### 5.4 Loading & Empty States

| | |
|---|---|
| **Connecting** | Centered spinner + "Connecting to observer..." — only shown before first SSE event |
| **No session** | Centered: "No active session. Run `/observer:start` in Claude Code." |
| **Empty graph** | Cytoscape canvas with single Session node, label "Waiting for agents..." |
| **Query loading** | Inline spinner in Ask button · results area shows skeleton rows |
| **Query empty** | "No results" — plain text, not an error state |
| **Disconnected** | Top bar shows red status · banner: "Reconnecting..." with attempt count |

---

## 6. Interaction Patterns

### 6.1 SSE Reconnection

- On disconnect: auto-retry with exponential backoff (1s, 2s, 4s, 8s, max 30s)
- Top bar status updates to show reconnect attempt number
- On reconnect: re-fetch current session graph to fill any missed events
- If reconnection fails after 5 attempts: show manual "Retry" button

### 6.2 Session Switching

- Clicking a session in Session History switches all views to that session's data
- Active session always shown first in session list with LIVE badge
- Session switch is instant — data is fetched on demand, not preloaded
- Archive banner persists across all views until "Return to live" is clicked

### 6.3 Keyboard Navigation

| Shortcut | Action |
|---|---|
| `Cmd+1` through `Cmd+6` | Switch between views |
| `Cmd+Enter` | Submit query in Query Console |
| `Escape` | Close slide-in panels, collapse expanded rows |
| `Space` | Toggle pause on Tool Feed |
| `/` | Focus query input (Query Console view) |

---

## 7. Responsive Behavior

| Breakpoint | Sidebar | Layout changes |
|---|---|---|
| < 900px (split screen) | Icon-only (56px) | Stat cards 1 col · Gantt labels truncate more aggressively |
| 900–1200px (laptop) | Expanded (200px) | Stat cards 2×2 · Standard layout |
| > 1200px (wide / 2nd monitor) | Expanded (200px) | Stat cards 4 across · Spawn Tree panel wider |

> **Designer decision:** The sidebar may become a top tab bar below 900px if that reads better at narrow widths — either approach is acceptable.

---

## 8. Handoff Notes

### What is pre-decided

- Dark theme — non-negotiable, developer tool context
- Teal (`#0A9396`) as primary color — matches LadybugDB brand
- Cytoscape.js for graph rendering — styling controllable via stylesheet
- SvelteKit + Tailwind for implementation
- 6 views as specified — scope is fixed for v0.1
- Read-only — no buttons that cause side effects

### What is open to designer

- Exact layout of top bar and sidebar — could be top nav at narrow widths
- Stat card visual design — numbers are specified, visual treatment is not
- Gantt bar visual style — tick marks and bar shapes specified, aesthetic is open
- Animation easing and duration within the constraints noted per-component
- Iconography — any consistent icon set (Heroicons, Lucide, Phosphor)
- Font weight choices within the Inter family
- Whether slide-in panels overlay or push content

### Deliverable Request

- Figma file with all 6 views at 1280px width
- Component library frame: badges, stat cards, event rows, node styles, buttons, inputs
- One narrow breakpoint frame (<900px) for the Spawn Tree view
- Design tokens exported as CSS custom properties
- Annotated handoff with spacing measurements on at least Spawn Tree and Tool Feed views

---

*CC Observer Dashboard UI Spec v0.1 — for designer handoff*
