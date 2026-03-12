# Multi-Session Overview

> See all active and recent Claude Code sessions at once, grouped by repo. Click to zoom into any session's execution graph.

---

## Problem

I routinely run 5-10 Claude Code sessions across multiple terminal windows, different repos, sometimes multiple clones of the same repo. The current dashboard assumes one active session at a time. The session store tracks a single `activeSessionId`. The SSE stream pushes all events from all sessions into one pipe, but the UI only renders one session's graph.

The result: I have to manually switch sessions in the Session History view to see what's happening elsewhere. There's no way to get a quick read on "what's running, where, right now?" without clicking through each session individually. That's the opposite of observability.

## Solution

A new top-level "Galaxy View" that renders all sessions on a shared time axis, grouped by workspace in horizontal swim lanes.

---

## UX Design

### Layout: Temporal Swim Lanes

The Galaxy View uses a **swim lane timeline** — horizontal lanes per workspace, sessions rendered as duration bars on a shared time axis. Think Gantt chart, but for Claude Code sessions.

Why swim lanes over the alternatives:

- **Sessions are temporal intervals, not points.** They have start times, end times, and varying durations. A time axis is the natural encoding. Card grids throw this away.
- **Temporal overlap is the thing you're looking for.** Which sessions ran concurrently? Where was I context-switching? Swim lanes answer this at a glance. Cards can't.
- **Workspace grouping is natural.** Each lane is a workspace. No compound graph layout to fight with, no CSS grid that looks like every other dashboard.
- **The uPlot time brush integrates directly.** The brush controls the visible time window — same axis, same coordinate space. With a card grid you'd need a separate, disconnected time filter.
- **It scales.** 10 workspaces = 10 lanes. 50 sessions = 50 bars. The layout doesn't break because the time axis absorbs density and the brush lets you zoom.

What it's NOT: a Gantt chart for project management. No task dependencies, no critical path, no resource leveling. It's a temporal map of where your attention went.

### Visual Description

```
+------------------------------------------------------------------------+
| CC Observer                                       [5 active] [SSE ●]   |
+------------------------------------------------------------------------+
| ◀ Galaxy View                                                          |
+------------------------------------------------------------------------+
|                                                                        |
| Time Brush (uPlot)                                                     |
| ┌────────────────────────────────────────────────────────────────────┐  |
| │▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│  |
| │          [=====selected range======]                               │  |
| └────────────────────────────────────────────────────────────────────┘  |
| 10:00        11:00        12:00        13:00        14:00     now       |
|                                                                        |
+--- Swim Lanes (within selected time range) ---------+------ Detail ---+
|                                                      |                 |
| observable-claude  2 active · 4 total                | Session Detail  |
| ─────────────────────────────────────────────────    |                 |
|  ███████████████████████████████████▓▓▓▓▓▓▓▓▓▓▓▓▓→  | sess_a1         |
|    ████████████████████████████████████████▓▓▓▓▓▓→   | LIVE · 47m      |
|      ████████████████████████                        | main            |
|                     █████████████████                | 4 agents        |
|                                                      | 127 events      |
| wolfpack  1 active · 1 total                         |                 |
| ─────────────────────────────────────────────────    | ● ● ●           |
|  ██████████████████████████████████████████████▓▓→   |  ╲│╱            |
|                                                      | ● ● ●           |
| dt-core  0 active · 2 total                          |  ╲│             |
| ─────────────────────────────────────────────────    | ●               |
|      ████████████████                                |                 |
|                        ██████████████                | [Open Tree →]   |
|                                                      |                 |
+------------------------------------------------------+-----------------+
```

### Anatomy of the View

**1. Time Brush (top, 64px)**

A uPlot sparkline showing event density over the full available time range. Drag to select a window. The sparkline is a stacked area: one color for each workspace, so you can see which repos had activity when. The selected range controls what the swim lanes below display.

Default range: last 4 hours, or the full range of sessions in the current recency window — whichever is shorter. Drag the selection edges to resize. Drag the selection body to pan. Double-click to reset to default.

**2. Workspace Lanes (left, flexible width)**

Each workspace gets a horizontal swim lane. Lanes are stacked vertically, sorted by most-recent-activity-first (workspaces with active sessions sort to top).

Lane header (left-aligned, 32px height):
- Workspace name (last path segment, bold, 14px Inter)
- Full path on hover (tooltip)
- Active count / total count (muted, right of name)
- Collapse toggle (chevron, click to hide lane body)

Lane body:
- Sessions rendered as horizontal bars on the shared time axis
- Each session bar occupies its own row within the lane (no overlapping)
- Bars stack vertically within the lane, ordered by start time (earliest on top)
- Lane auto-sizes height to fit all session bars

**3. Session Bars**

The core visual element. Each bar represents one session's temporal extent.

| Property | Visual Encoding |
|---|---|
| Duration | Bar length (proportional to time axis) |
| Status: active | Right edge is a gradient fade from solid to transparent — the bar is "still growing." 2px animated teal border on right edge. |
| Status: complete | Solid bar, squared right edge, muted color. |
| Status: failed | Coral left border (4px). |
| Depth (agent count) | Bar height: 24px base + 2px per agent, max 40px. More agents = thicker bar. |
| Event density | Bar fill uses a subtle heat gradient — darker segments where events cluster, lighter where the session was idle. Not a separate chart, just texture within the bar. |

Bar content (rendered inline, clipped to bar width):
- Session ID (truncated, monospace, 11px)
- Branch name if available (muted, 11px)
- Agent count badge (right-aligned within bar, if bar is wide enough)

If the bar is too narrow to show text (< 80px at current zoom), show only the colored bar with a tooltip on hover.

**4. Detail Panel (right, 320px, slide-in)**

Click any session bar to open the detail panel. Same interaction pattern as the Spawn Tree node detail panel — 320px slide-in from right, `Escape` to close.

Panel contents:
- Session ID (monospace, full)
- Status badge (LIVE with pulsing dot, or completion timestamp)
- Workspace path
- Branch name
- Start time (absolute + relative)
- Duration (live counter if active)
- Agent count (with spawn depth)
- Event count
- Mini spawn tree: a tiny Cytoscape.js canvas (200px tall) showing the session's spawn tree at that moment. Not interactive — just a shape preview. Session node at top, agent nodes as circles sized by tool count. Same color encoding as the full Spawn Tree view.
- `[Open Spawn Tree]` button — navigates to `/tree/{session_id}`
- `[Open Timeline]` button — navigates to `/timeline/{session_id}`

### Color System

Session bars use the existing palette with a few additions:

| State | Bar Color | Border |
|---|---|---|
| Active session | `--color-primary` (#0A9396) at 80% opacity | 1px `--color-border` top/bottom, animated 2px teal right edge |
| Completed session | `--color-surface-2` (#2D3E50) | 1px `--color-border` |
| Failed session | `--color-surface-2` (#2D3E50) | 4px `--color-error` left border |
| Hovered (any) | Lighten fill 10%, show full session ID tooltip | 1px `--color-primary` |
| Selected (detail open) | Original fill | 2px `--color-primary` all sides |

Workspace lane headers: `--color-surface` background. Lane body: transparent (bars sit on the `--color-bg` navy).

Lane separators: 1px `--color-border` horizontal lines between workspace lanes.

### Interaction Model

**Hover**
- Hover over a session bar: tooltip shows session ID, duration, agent count, branch. Bar lightens slightly.
- Hover over the time brush: vertical crosshair shows the timestamp.
- Hover over a workspace header: highlight the entire lane with a subtle background tint.

**Click**
- Click a session bar: open the detail panel (right). The bar gets a teal border. Only one bar selected at a time.
- Click `[Open Spawn Tree]` in detail panel: navigate to `/tree/{session_id}`.
- Click a workspace name: collapse/expand that lane.
- Click empty space: close the detail panel.

**Keyboard**
- `↑`/`↓`: move selection between session bars (within and across lanes)
- `←`/`→`: pan the time brush window
- `Enter`: open Spawn Tree for the selected session
- `Escape`: close detail panel, deselect
- `Cmd+0`: navigate to Galaxy View from any other view

**Drag**
- Drag on the time brush: select a time range
- Drag the time brush selection edges: resize the window
- Drag the time brush selection body: pan the window
- Double-click the time brush: reset to default range

### Time Brush Integration

The uPlot instance at the top is the time authority for the entire view.

- The sparkline data source is `event_count` per 30-second bucket, aggregated across all sessions, stacked by workspace.
- The brush selection defines the visible time window for the swim lanes below.
- Session bars that extend beyond the selected window are clipped but still visible (they extend to the edge with a fade).
- As active sessions generate events, the sparkline updates in real-time and the "now" edge of the brush advances.
- The time axis labels on the swim lanes match the brush selection range.

**Performance note:** uPlot renders the sparkline in a single canvas pass. No DOM elements per data point. The swim lane bars below are rendered as absolutely-positioned `<div>` elements — one per session, not a canvas. This keeps them individually interactive (hover, click) while the time brush stays fast.

### Active vs Completed Sessions

| Signal | Active | Completed |
|---|---|---|
| Bar color | Teal (80% opacity) | Dark gray (`--color-surface-2`) |
| Right edge | Gradient fade + animated 2px teal border (bar is growing) | Hard edge (bar is final) |
| Bar height | 24-40px (scales with agent count, which may still be changing) | 24-40px (fixed) |
| Lane sort | Active sessions' workspace lanes sort to top | Completed-only lanes sort below |
| Time brush | Active sessions extend to "now" on the sparkline | Fixed interval on the sparkline |
| Detail panel | Live duration counter, "LIVE" badge with pulsing dot | Static duration, completion timestamp |

New sessions appear with a brief 300ms entrance animation — the bar slides in from the left edge and the workspace lane header flashes the active count update. If the session's workspace is collapsed, the lane auto-expands.

### Workspace Grouping

Workspaces are identified by the `cwd` from `SessionStart`. Two clones of the same repo at different paths are separate workspaces (by design — you might be on different branches).

Lane ordering:
1. Workspaces with active sessions, sorted by most-recent-session-start
2. Workspaces with only completed sessions, sorted by most-recent-session-end

Each workspace lane is independently collapsible. Collapsed state: header only (32px), with a mini-bar preview — tiny colored segments inline in the header showing the session density pattern (like a GitHub contribution strip). Click to expand.

### Responsive Behavior

| Breakpoint | Detail Panel | Time Brush | Lanes |
|---|---|---|---|
| < 900px | Full-width overlay (not side panel) | Height reduced to 48px, simplified sparkline | Session bars show no inline text, tooltip only |
| 900-1200px | 280px side panel | Standard 64px | Session bars show truncated ID |
| > 1200px | 320px side panel | Standard 64px | Session bars show ID + branch + agent count |

Below 900px, the detail panel becomes a bottom sheet (slides up from bottom, 50% viewport height) rather than a side panel. The swim lanes get full width.

### States

| State | Display |
|---|---|
| **Empty** (no sessions) | Full-width message: "No sessions observed. Start a Claude Code session to begin." Observatory illustration (subtle, on-brand). |
| **Loading** | Time brush skeleton (gray gradient bar). 3 lane skeletons with gray bar placeholders. |
| **Populated** | Full swim lane layout as described. |
| **Error** (API failure) | Banner at top: "Failed to load sessions. [Retry]" with `--color-error` background. |
| **Overflow** (50+ sessions) | Time brush stays performant (aggregated data). Swim lanes virtualize — only render lanes and bars visible in the scroll viewport. Collapsed lanes by default when > 8 workspaces. |

### Component Breakdown

```
GalaxyView/
├── GalaxyView.svelte          — top-level container, data fetching, keyboard handler
├── TimeBrush.svelte           — uPlot sparkline with brush selection
├── SwimLaneContainer.svelte   — scrollable lane container, virtualization
├── WorkspaceLane.svelte       — single workspace: header + session bars
├── SessionBar.svelte          — individual session bar with hover/click
├── SessionDetail.svelte       — right panel (reuses patterns from SpawnTree detail)
├── MiniSpawnTree.svelte       — tiny Cytoscape.js preview in detail panel
└── GalaxyEmpty.svelte         — empty state
```

**Store additions:**

```typescript
// workspace.ts
export const workspaces = writable<WorkspaceGroup[]>([]);
export const selectedSessionId = writable<string | null>(null);
export const timeRange = writable<{ start: number; end: number } | null>(null);
export const collapsedWorkspaces = writable<Set<string>>(new Set());
```

**Data flow:**

1. On mount, `GalaxyView` fetches `GET /api/sessions/grouped` and populates the `workspaces` store.
2. `TimeBrush` subscribes to the workspace store to build the stacked sparkline data.
3. User brush interaction updates `timeRange`.
4. `SwimLaneContainer` filters sessions by `timeRange` and renders `WorkspaceLane` components.
5. SSE events update the `workspaces` store in real-time (new sessions appear, event counts increment, sessions complete).
6. Click on a `SessionBar` sets `selectedSessionId`, opening `SessionDetail`.

---

## Schema Changes

### Graph Schema (LadybugDB)

**New Workspace node** — represents a unique `cwd` path:

```sql
CREATE NODE TABLE Workspace (
    path STRING,
    name STRING,
    PRIMARY KEY (path)
);

CREATE REL TABLE CONTAINS (
    FROM Workspace TO Session,
    first_seen STRING
);
```

The `name` property is the last path segment — convenience for display. `CONTAINS` links workspaces to their sessions with a `first_seen` timestamp.

**Why a node and not just a grouping query?** Cross-session queries become natural: "show me all sessions in this repo", "which tools are used most in this workspace", "compare agent patterns across repos." Without a Workspace node, every cross-session query starts with `WHERE s.cwd = '...'` string matching. With it, you traverse `(w:Workspace)-[:CONTAINS]->(s:Session)`.

**Materialization**: `SessionStart` handler creates the Workspace node (MERGE on path) and the CONTAINS edge. Minimal change — one new MERGE per session start.

### DuckDB

No schema changes needed. The `cwd` column on the `events` table already supports the grouping query. Add one index:

```sql
CREATE INDEX IF NOT EXISTS idx_cwd ON events(cwd);
```

### API Changes

#### New Endpoints

**`GET /api/sessions/grouped`**

Sessions grouped by cwd, with aggregate stats per group. Supports `?since=` query param for recency filtering (ISO timestamp, default: 24 hours ago).

```json
[
  {
    "workspace": "/Users/matt/gh/me/ai/observable-claude",
    "name": "observable-claude",
    "sessions": [
      {
        "session_id": "sess_a1",
        "is_active": true,
        "start_time": "2026-03-12T10:30:00Z",
        "end_time": null,
        "agent_count": 4,
        "event_count": 127,
        "branch": "main",
        "max_depth": 3
      }
    ],
    "active_count": 2,
    "total_count": 3
  }
]
```

**`GET /api/sessions/activity`**

Time-bucketed event counts for the time brush sparkline. Returns 30-second buckets, stacked by workspace.

```json
{
  "bucket_seconds": 30,
  "buckets": [
    {
      "timestamp": "2026-03-12T10:00:00Z",
      "counts": {
        "/Users/matt/gh/me/ai/observable-claude": 14,
        "/Users/matt/gh/me/legal/wolfpack": 3
      }
    }
  ]
}
```

#### Modified Endpoints

**`GET /stream`** — no protocol change, but the dashboard needs to handle events from N sessions simultaneously. The SSE stream already includes `session_id` on every event. The client-side change is routing events to the correct session's state rather than assuming one active session.

**`GET /api/sessions`** — add `is_active`, `agent_count`, `branch`, and `max_depth` to each session object (avoids N+1 queries from the dashboard).

### Dashboard Changes

#### New Store: `workspace.ts`

```typescript
// Workspace grouping of sessions
export const workspaces = writable<WorkspaceGroup[]>([]);
export const selectedSessionId = writable<string | null>(null);
export const timeRange = writable<{ start: number; end: number } | null>(null);
export const collapsedWorkspaces = writable<Set<string>>(new Set());
```

#### Modified Store: `session.ts`

The `activeSessionId` stays but becomes "which session am I drilled into." New concept: `activeSessions` (plural) — all sessions currently receiving events. The store tracks multiple live sessions and routes SSE events to the correct one.

#### SSE Client Changes

`sse.ts` currently sets `liveSessionId` to the latest `SessionStart`. In multi-session mode, it needs to track a *set* of live session IDs and update the appropriate session's state when events arrive. The `SessionStart` handler adds to the set; `SessionEnd` removes.

#### Routing

| Route | View |
|---|---|
| `/galaxy` | Galaxy View (all sessions, grouped) |
| `/tree` | Spawn Tree (current — uses activeSessionId) |
| `/tree/{session_id}` | Spawn Tree for specific session |
| `/timeline/{session_id}` | Timeline for specific session |

Galaxy View becomes the new default route when 2+ sessions exist.

---

## Implementation Phases

### Phase 1: Multi-Session Data Layer

Backend changes to support grouped session queries and the Workspace graph node. No dashboard changes yet — everything testable via API.

- Add Workspace node to LadybugDB schema
- Add CONTAINS relationship
- Update SessionStart handler to MERGE Workspace + CONTAINS
- Add `GET /api/sessions/grouped` endpoint
- Add `GET /api/sessions/activity` endpoint (time-bucketed counts for sparkline)
- Add `cwd` index to DuckDB
- Update `GET /api/sessions` response to include `is_active`, `agent_count`, `branch`, `max_depth`
- Update replay.py to handle Workspace materialization

### Phase 2: Multi-Session Dashboard Store

Refactor the dashboard to track multiple sessions simultaneously. No new views yet — this is the plumbing.

- Refactor `session.ts` to support multiple active sessions
- Refactor `sse.ts` to route events by session_id
- Add `workspace.ts` store
- Add `fetchGroupedSessions` and `fetchActivity` API client functions
- Wire up session-specific routing (`/tree/{session_id}`)

### Phase 3: Galaxy View — Time Brush + Swim Lanes

The new overview UI.

- `TimeBrush` component with uPlot sparkline and brush selection
- `SwimLaneContainer` with virtualized scrolling
- `WorkspaceLane` with collapsible headers and session bar layout
- `SessionBar` with status encoding, hover tooltips, click-to-select
- `SessionDetail` panel with mini spawn tree preview
- Breadcrumb bar integration
- Auto-highlight on new SessionStart events
- Keyboard navigation (arrow keys, Enter, Escape)

### Phase 4: Polish and Edge Cases

- Handle sessions that change `cwd` mid-session (use first `cwd`)
- Session recency cutoff for Galaxy View (default 24h, configurable)
- Responsive layout (bottom sheet on mobile, reduced sparkline)
- SSE reconnection with multi-session state recovery
- Overflow handling: lane virtualization, auto-collapse at 8+ workspaces
- Empty state illustration

---

## Resolved Questions

1. **Recency window** — Default 24 hours. The `?since=` param on `/api/sessions/grouped` makes it configurable. Active sessions always show regardless of recency.
2. **Branch detection** — Captured at session start via `git rev-parse --abbrev-ref HEAD` in the hook. Stored as session metadata. Displayed in session bars and detail panel.
3. **Session migration** — Use `cwd` from `SessionStart` for grouping. Mid-session `cd` doesn't change the workspace assignment. Simple, deterministic.
4. **Galaxy View layout** — Swim lanes on a shared time axis. Not compound dagre, not CSS grid cards. Temporal data gets a temporal layout.

---

## Dependencies

- Existing: Session History view (#6 view), SSE infrastructure, Cytoscape.js setup
- New: uPlot dependency for the time brush sparkline
- Related: Session Save/Bookmark (#10) — saved sessions should appear in Galaxy View with bookmark indicators
- No blockers — the current schema and infrastructure support this; it's additive
