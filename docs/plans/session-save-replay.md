# Session Save & Replay

> Save interesting sessions, load them later with full fidelity, share them as portable files, replay events like a recording.

---

## Problem

CC Observer captures everything to DuckDB and materializes the graph in LadybugDB. But there's no concept of "this session matters, I want to keep it." When the Docker stack restarts, LadybugDB may be in a different state. The dashboard can list past sessions from DuckDB, but it can't:

- Bookmark a session for easy access later
- Guarantee the graph state matches what you saw live
- Export a session for someone else to import and explore
- Play back events chronologically to watch how a session unfolded

The Session History view gets you halfway — you can click past sessions and see their data. But "find the interesting one from Tuesday" requires scrolling through every session. And sharing means "give someone your DuckDB file," which is neither practical nor scoped.

---

## Solution

Four capabilities, built incrementally:

### 1. Save/Bookmark Sessions

Tag sessions with a user-defined name and optional notes. Saved sessions appear in a dedicated "Saved Sessions" section of Session History, sorted by save date. Metadata stored in DuckDB — no new service.

### 2. Session Snapshot Export

Export a session as a self-contained `.ccobs` file (JSON-based archive). Contains:
- Session metadata (id, name, timestamps, notes)
- All DuckDB events for that session (full payloads)
- Graph snapshot (nodes + edges as Cytoscape JSON, same format `/api/sessions/{id}/graph` already returns)
- Timeline data
- Analytics summary (precomputed so the recipient doesn't need the full stack)

The file is everything needed to render all 6 dashboard views for that session. No DuckDB or LadybugDB required on the viewing end.

### 3. Session Import

Import a `.ccobs` file. Events go into DuckDB (deduplicated by event_id). Graph is materialized via the existing replay path. The session appears in Saved Sessions automatically.

### 4. Event Replay / Playback

Replay a session's events in chronological order at configurable speed. The dashboard renders events as if they were arriving live — nodes appear, edges form, timeline bars extend. Think git log animation or a recorded demo.

This reuses the existing SSE infrastructure. The collector emits stored events on a replay SSE channel at the configured playback rate. The dashboard connects to the replay stream instead of the live stream.

---

## Schema Changes

### DuckDB

```sql
CREATE TABLE saved_sessions (
  session_id    VARCHAR PRIMARY KEY REFERENCES events(session_id),
  name          VARCHAR NOT NULL,
  notes         TEXT,
  saved_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  tags          JSON,            -- ["debug", "multi-agent", "interesting-failure"]
  export_count  INTEGER DEFAULT 0
);

CREATE INDEX idx_saved_at ON saved_sessions(saved_at);
```

No changes to the `events` table. Saved sessions are metadata on top of existing event data.

### LadybugDB

No schema changes. The graph is rebuilt from DuckDB events via existing replay infrastructure. Saved session metadata lives in DuckDB only — it's not graph-shaped data.

---

## API Changes

### New Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/sessions/{id}/save` | Save/bookmark a session |
| `DELETE` | `/api/sessions/{id}/save` | Remove bookmark |
| `GET` | `/api/sessions/saved` | List saved sessions |
| `PATCH` | `/api/sessions/{id}/save` | Update name/notes/tags |
| `GET` | `/api/sessions/{id}/export` | Download `.ccobs` file |
| `POST` | `/api/sessions/import` | Upload and import `.ccobs` file |
| `POST` | `/api/sessions/{id}/replay` | Start replay on a dedicated SSE channel |
| `GET` | `/api/sessions/{id}/replay/stream` | SSE endpoint for replay events |
| `POST` | `/api/sessions/{id}/replay/control` | Play/pause/speed/seek |

### Modified Endpoints

| Endpoint | Change |
|---|---|
| `GET /api/sessions` | Add `saved` query param to filter saved-only |
| `GET /api/sessions/{id}/graph` | Works unchanged — already returns Cytoscape JSON |

---

## `.ccobs` File Format

```json
{
  "version": 1,
  "format": "cc-observer-session",
  "exported_at": "2026-03-12T...",
  "session": {
    "session_id": "...",
    "name": "Multi-agent planning debug",
    "notes": "Interesting failure in specialist dispatch",
    "start_ts": "...",
    "end_ts": "...",
    "tags": ["debug", "multi-agent"]
  },
  "events": [
    { "event_id": "...", "event_type": "SessionStart", "received_at": "...", "payload": {...} },
    ...
  ],
  "graph": {
    "nodes": [...],
    "edges": [...]
  },
  "timeline": [...],
  "analytics": {
    "agent_count": 6,
    "tool_call_count": 47,
    "duration_ms": 124000,
    "tool_success_rate": 0.94,
    "p95_latency_ms": 3200
  }
}
```

Gzipped on export (`.ccobs` is gzipped JSON). Typical session: 50-500 KB compressed.

---

## Dashboard UX Changes

### Session History View

- **Saved Sessions** section at the top, pinned. Shows name, save date, tags, notes preview.
- Star/bookmark icon on every session row — click to save, click again to unsave.
- Search/filter saved sessions by name and tags.
- Export button on saved session rows (downloads `.ccobs`).
- Import button in the header (file upload).

### Replay Controls

When viewing a saved or historical session, a replay toolbar appears at the bottom of the dashboard:

- Play/Pause button
- Speed selector: 1x, 2x, 5x, 10x, max
- Timeline scrubber (seek to any point)
- Event counter: "Event 23 of 147"
- Current timestamp display

During replay, all views update as events arrive — Spawn Tree animates, Timeline bars extend, Tool Feed populates, Analytics update in real-time. Same rendering path as live sessions, different event source.

### Session Detail Header

When viewing a saved session, the header shows the saved name, notes, and tags (editable inline). Non-saved sessions show session_id and timestamps as they do today.

---

## Replay Architecture

The replay system reuses existing infrastructure rather than building a parallel rendering path:

1. **Collector replay endpoint** reads events from DuckDB for a session, ordered by `received_at`.
2. Events are emitted on a session-specific SSE channel at the configured playback rate.
3. Dashboard connects to the replay SSE stream using the same event handlers it uses for live events.
4. Playback state (position, speed, paused) tracked server-side per replay session.
5. Client sends control commands (play, pause, seek, speed) via the control endpoint.

This means every dashboard view "just works" during replay — no dual rendering code. The only new UI is the playback controls toolbar.

**Seek**: Jump to event N means the collector emits events 1-N instantly (batch mode), then resumes timed playback from N+1. The dashboard handles the burst the same way it handles catching up on reconnection to a live stream.

---

## Implementation Phases

### Phase 1: Save/Bookmark (foundation)

DuckDB `saved_sessions` table. Save/unsave API endpoints. Dashboard bookmark UI in Session History. Simple, self-contained, immediately useful.

### Phase 2: Export/Import

`.ccobs` file format. Export endpoint assembles the archive from DuckDB + collector APIs. Import endpoint writes events to DuckDB and triggers selective replay. Dashboard export/import buttons.

### Phase 3: Event Replay

Replay SSE channel. Playback control API. Dashboard replay toolbar. This is the largest phase — it needs careful timing logic and dashboard integration.

---

## What's Out of Scope

- **Collaborative/cloud sharing** — `.ccobs` files are shared manually (Slack, email, git). No hosted sharing service.
- **Partial session export** — Export is always the full session. Time-range filtering is a future enhancement.
- **Replay with live overlay** — Replay is a dedicated mode, not mixed with live session data.
- **Annotation/commenting on saved sessions** — Name and notes are enough for v1. Full annotation is a separate feature.
- **Auto-save rules** — No "save all sessions longer than 5 minutes" automation. Manual save only for v1.

---

## Open Questions

1. **Import dedup strategy** — If someone imports a `.ccobs` file for a session that already exists in DuckDB, do we skip (idempotent by event_id), overwrite, or create a copy? Recommendation: skip existing events by event_id. The saved_sessions metadata gets upserted.

2. **Replay graph state** — During replay, should we materialize the graph incrementally in LadybugDB (accurate but mutates state), or render purely from the Cytoscape JSON snapshots in the export file (read-only but may miss query capability)? Recommendation: render from snapshots for imported sessions, use live materialization for locally-stored sessions where LadybugDB is available.

3. **Max export size** — Long sessions with many tool calls could produce large exports. Should we cap at a size threshold, or warn and proceed? Recommendation: warn if >50 MB, proceed anyway.
