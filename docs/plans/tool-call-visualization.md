# Tool Call Visualization

> Tool calls are the primary unit of work in Claude Code. Make them a first-class visual citizen across every dashboard view.

---

## Problem

Tool calls are how Claude Code *does things* — Read, Write, Edit, Bash, Grep, Agent, MCP calls. The graph already captures them as `Agent -[INVOKED]-> Tool` relationships with duration, status, input, and response. But the dashboard treats them as second-class data:

- **Tool Feed** is a flat chronological log. No context about which agent made the call, no visual grouping, no pattern recognition. It answers "what just happened" but not "what is this agent doing."
- **Timeline** renders tool calls as 2px tick marks on agent bars. Technically present, practically invisible. You can't read them, can't distinguish types, can't spot failures without squinting.
- **Spawn Tree** reduces an agent's entire tool history to a single number on hover. "Tools: 47" tells you nothing about whether those were 47 file reads or 47 failed MCP calls.
- **Galaxy View** doesn't surface tool calls at all — appropriate for the overview level, but there's no way to see tool activity patterns even as aggregate signals.

The result: to understand what an agent is actually *doing*, you have to leave the structural views and dig through the Tool Feed log. That's the opposite of observability.

---

## Tool Family Taxonomy

Claude Code tools fall into five families. Each family represents a different *kind* of work, and the visual language should make that distinction immediate.

| Family | Tools | Character | Icon | Color Token |
|---|---|---|---|---|
| **File** | Read, Write, Edit, Glob, Grep | Filesystem interaction — reading, writing, searching files | Document glyph | `--tool-file` `#7EB8DA` (steel blue) |
| **Exec** | Bash | Shell execution — running commands, scripts, processes | Terminal glyph | `--tool-exec` `#B8A9E8` (lavender) |
| **Agent** | Agent | Orchestration — spawning subagents | Network glyph | `--tool-agent` `#0A9396` (teal, reuses primary) |
| **MCP** | mcp__* | External services — third-party integrations via MCP | Plug glyph | `--tool-mcp` `#E8A87C` (peach) |
| **Meta** | TodoRead, TodoWrite, TaskCreate, etc. | Internal bookkeeping — task tracking, memory, planning | Clipboard glyph | `--tool-meta` `#94D2BD` (mint, reuses success) |

### Why these five

- **Cardinality**: Five families stay within the 8-category limit for color hue discrimination (per visual encoding rules). More granular breakdown (separating Read from Write, for instance) would require shape or position encoding on top of color — too much visual weight for at-a-glance scanning.
- **Semantic coherence**: Each family represents a meaningfully different *type of interaction*. File ops are filesystem. Bash is execution. Agent is orchestration. MCP is external. Meta is internal state. A user looking at an agent's tool call pattern cares about the *mix* of these categories — "mostly file reads" vs "heavy bash execution" vs "lots of MCP calls" are different profiles with different implications.
- **Classification is unambiguous**: Every tool name maps to exactly one family. No edge cases, no "it depends." MCP tools are identifiable by the `mcp__` prefix. Agent is a single tool. Everything that's not Bash, Agent, or mcp__* is either a known file op or falls into Meta.

### Color Rationale

The five tool family colors are chosen to be:
- **Distinguishable from each other** on the dark navy background
- **Distinguishable from the existing status colors** (teal/running, gray/complete, coral/failed, amber/warning) — the tool family palette lives in a different hue range to avoid confusion with status encoding
- **Accessible** — each pair passes WCAG AA contrast against `--color-bg` (#0D1B2A) and against each other at the sizes we'll use (12px+ for icons, 8px+ for dots)

Agent family reuses teal because agent spawning is already visually encoded as teal in the spawn tree — consistency matters more than distinctness here.

---

## Visual Language

### The Tool Pip

The atomic visual unit for tool calls across all views: a small shape that encodes **family** (color), **status** (fill), and optionally **duration** (size).

**Default**: 8px circle, solid fill, family color.

| Status | Visual Treatment |
|---|---|
| Success | Solid fill, family color |
| Failed | Family color fill + 1px coral ring |
| Pending | Family color at 40% opacity, pulsing |

**Duration encoding** (optional, per-view): For views with space, pip diameter scales from 6px (fast, <100ms) to 14px (slow, >2s). Duration outliers — calls above p95 for that tool — get a subtle outer glow in amber to draw the eye.

### The Tool Strip

A horizontal sequence of pips — the tool call history for a single agent, rendered as a compact inline visualization. Think of it as a miniature genome browser: each pip is a tool call, left-to-right in chronological order, colored by family.

Width: flexible (fills available space). Pip spacing: 2px gap. Overflow: fade-out gradient on the right edge when calls exceed available width, with a "+N" count.

The strip is the bridge between "here's a number" (current) and "here's a detailed log" (tool feed). At a glance, you see the *pattern* of work: a wall of blue = file-heavy agent. Alternating blue and purple = read-then-execute pattern. A red-ringed pip = something failed.

---

## Per-View Integration

### Spawn Tree

The spawn tree becomes tool-aware without becoming cluttered. Two changes:

**1. Tool strip in the detail panel**

When you click an agent node, the existing 320px detail panel currently shows a tools section as a name/count list. Replace that with a tool strip (full width of the panel) above the count list. The strip gives you the *pattern*; the list below gives you the *numbers*.

Add below the strip:
- Family breakdown bar: a single horizontal stacked bar (12px tall) showing the proportion of each tool family. Hovering a segment highlights just that family's pips in the strip above.
- A "View in Tool Feed" link that navigates to Tool Feed pre-filtered to this agent's calls.

**2. Tool call satellite ring on agent nodes**

On the graph canvas itself, each agent node gets a subtle ring of tool pips arranged in a circle around the node perimeter. The ring uses the same family colors as the tool strip.

Rules:
- Only show the ring when the node has tool calls (obvious, but stated for completeness)
- Max 24 pips in the ring — if an agent has more, show the most recent 24 with a gap indicator
- Ring radius: node width/2 + 8px
- Pips in the ring are 4px (smaller than standard) to avoid overwhelming the graph layout
- Failed pips get the coral ring treatment even at 4px — failures must always be visible
- The ring is hidden at zoom levels below 0.6x to keep the overview clean

**Interaction**: Hover a pip in the ring → tooltip with tool name, timestamp, duration, status. Click a pip → opens the detail panel with that tool call's EventRow expanded.

### Timeline (Gantt)

The timeline currently renders tool calls as uniform 2px teal/coral ticks. Three improvements:

**1. Colored ticks by family**

Replace monochrome ticks with family-colored ticks. The existing 2px x 12px tick geometry stays — it works at this scale. Just apply the tool family color instead of flat teal.

Failed ticks keep coral regardless of family (status > family for failures).

**2. Expandable tool rows**

Click an agent row in the timeline to expand it. The expanded state shows individual tool calls as mini-bars within the agent's time span, one row per concurrent tool call. Each mini-bar:
- Colored by tool family
- Width proportional to duration on the time axis
- Label: tool name (if bar is wide enough, >60px)
- Height: 16px (half the agent row height)
- Gap between sub-rows: 2px

This turns the Gantt from "agents over time" into "agents and their work over time." Collapsed = the current view with colored ticks. Expanded = full tool call detail for that agent.

**3. Duration outlier highlighting**

Tool calls above p95 duration for that tool type get an amber left border (2px) on their mini-bar in expanded view, and a slightly taller tick (16px instead of 12px) in collapsed view. Slow calls should visually pop.

### Tool Feed

The tool feed is already the most complete tool call view. Three enhancements to connect it to the rest of the dashboard:

**1. Tool family color coding**

Add the tool family color as a secondary visual signal. Currently the 4px left border encodes event type (Pre/Post/Fail). Add a tool family color pip (8px circle) between the timestamp and the event type pill. This lets you scan the feed by family as well as by status.

**2. Agent context**

Add the agent type label to each event row (already partially there as muted text). Make it a clickable link: click the agent name → navigate to Spawn Tree with that agent node selected.

**3. Cross-view navigation**

Add a toolbar icon to each event row (on hover): "Show in Timeline" — navigates to Timeline view, scrolls to the agent, expands the tool row, and highlights the specific tool call. This closes the loop: you spot something interesting in the feed, one click to see it in temporal context.

### Galaxy View

At the Galaxy View level, individual tool calls are noise. But aggregate tool activity is a useful signal about what a session is *doing*.

**1. Tool density heatmap within session bars**

The session bar already uses a "subtle heat gradient" for event density. Extend this: the heat gradient segments are tinted by the dominant tool family in that time window. A session that's mostly reading files gets a blue-tinted heat gradient. A session running lots of bash commands gets a purple tint. Mixed activity stays the current neutral tint.

This is not a stacked bar chart within the session bar — that would be too busy at this scale. It's a tint, a hint. Just enough to answer "is this session mostly reading or mostly executing?"

**2. Failure indicator**

If a session has any failed tool calls, add a small coral dot (6px) at the right end of the session bar (or at the current "now" edge for active sessions). One signal: something failed in this session. Click the bar → detail panel shows the failure count and a "View failures" link to Tool Feed filtered to that session's failures.

**3. Detail panel tool summary**

The Galaxy View detail panel currently shows agent count and event count. Add a tool family breakdown: a small stacked bar (same as the one in Spawn Tree detail panel) showing the session-level tool family distribution. Below it, one-line stats: total tool calls, success rate, median duration.

---

## Interaction Model

### Progressive Disclosure

The tool call visualization follows a strict three-level disclosure pattern:

| Level | What You See | Where | Interaction |
|---|---|---|---|
| **Glance** | Family color pips, density tints, failure dots | All views | None — visible by default |
| **Scan** | Tool strip, family breakdown bar, aggregate stats | Detail panels (click to open) | Click agent/session |
| **Inspect** | Full tool input/response, expanded timeline rows, individual event details | Expanded rows, cross-view navigation | Click specific tool call |

### Cross-View Navigation

Tool calls are the connective tissue between views. Every tool call reference is navigable:

| From | Action | To |
|---|---|---|
| Spawn Tree pip ring | Click pip | Detail panel with tool call expanded |
| Spawn Tree detail panel | Click "View in Tool Feed" | Tool Feed filtered to agent |
| Timeline expanded row | Click mini-bar | Tool Feed scrolled to that event |
| Tool Feed row | Click agent name | Spawn Tree with agent selected |
| Tool Feed row | Click "Show in Timeline" | Timeline expanded to that call |
| Galaxy View detail | Click "View failures" | Tool Feed filtered to session failures |

### Keyboard

| Shortcut | Context | Action |
|---|---|---|
| `T` | Spawn Tree (node selected) | Toggle tool strip visibility in detail panel |
| `X` | Timeline (agent row focused) | Expand/collapse tool call sub-rows |
| `F` | Any view | Jump to Tool Feed (preserves current filters if applicable) |

---

## Component Breakdown

### New Components

```
ToolViz/
├── ToolPip.svelte           — atomic 8px circle, family color + status
├── ToolStrip.svelte          — horizontal pip sequence for an agent's tool history
├── ToolFamilyBar.svelte      — stacked horizontal bar showing family proportions
├── ToolSummary.svelte        — one-line stats (total, success rate, median duration)
├── ToolPipRing.svelte        — circular pip arrangement for Spawn Tree nodes
└── TimelineToolRow.svelte    — expandable sub-row for Timeline tool call detail
```

### Modified Components

| Component | Change |
|---|---|
| `NodeDetail.svelte` | Replace tools count list with ToolStrip + ToolFamilyBar + count list |
| `EventRow.svelte` | Add ToolPip before event type pill, add agent link, add "Show in Timeline" action |
| `+page.svelte` (tree) | Add ToolPipRing rendering to Cytoscape node extension layer |
| `+page.svelte` (timeline) | Add row expand/collapse, render TimelineToolRow, color ticks by family |
| `SessionDetail.svelte` (galaxy) | Add ToolFamilyBar + ToolSummary to detail panel |
| `SessionBar.svelte` (galaxy) | Add dominant-family tint to heat gradient, failure dot |
| `app.css` | Add tool family color tokens |

### Store Additions

```typescript
// tool-families.ts
export const TOOL_FAMILIES = {
  file: { tools: ['Read', 'Write', 'Edit', 'Glob', 'Grep'], color: '#7EB8DA', icon: 'document' },
  exec: { tools: ['Bash'], color: '#B8A9E8', icon: 'terminal' },
  agent: { tools: ['Agent'], color: '#0A9396', icon: 'network' },
  mcp: { prefix: 'mcp__', color: '#E8A87C', icon: 'plug' },
  meta: { tools: ['TodoRead', 'TodoWrite', 'TaskCreate', 'ToolSearch'], color: '#94D2BD', icon: 'clipboard' }
} as const;

export function getToolFamily(toolName: string): keyof typeof TOOL_FAMILIES {
  if (toolName.startsWith('mcp__')) return 'mcp';
  for (const [family, def] of Object.entries(TOOL_FAMILIES)) {
    if ('tools' in def && def.tools.includes(toolName)) return family as keyof typeof TOOL_FAMILIES;
  }
  return 'meta'; // unknown tools default to meta
}
```

---

## Implementation Phases

### Phase 1: Visual Language Foundation

Establish the design tokens and atomic components. No view changes yet — just the building blocks.

- Add tool family color tokens to `app.css`
- Build `ToolPip.svelte` (the atomic unit)
- Build `ToolStrip.svelte` (horizontal pip sequence)
- Build `ToolFamilyBar.svelte` (stacked proportion bar)
- Build `ToolSummary.svelte` (aggregate stats line)
- Create `tool-families.ts` store with classification logic
- Validate colors against WCAG AA on dark background

**Difficulty**: Routine (2/10). Clarity 0, Solution 0, Functional-Deps 0, Infra-Deps 0, Constraints 1 (color accessibility).

### Phase 2: Spawn Tree + Detail Panel Integration

The highest-impact change — seeing tool call patterns when you click an agent.

- Replace tools count list in `NodeDetail.svelte` with ToolStrip + ToolFamilyBar
- Add "View in Tool Feed" navigation link
- Build `ToolPipRing.svelte` for canvas-level rendering
- Integrate pip ring with Cytoscape node extension layer
- Handle ring visibility at different zoom levels
- Pip hover tooltips, pip click → detail panel scroll

**Difficulty**: Involved (4/10). Clarity 0, Solution 1 (Cytoscape extension layer is non-trivial), Functional-Deps 1, Infra-Deps 0, Constraints 1.

### Phase 3: Timeline Enhancement

Expand the timeline from agent-level to tool-level detail.

- Color existing ticks by tool family
- Build `TimelineToolRow.svelte` for expanded view
- Add row expand/collapse interaction to timeline canvas
- Render tool call mini-bars within expanded rows
- Duration outlier highlighting (amber border, taller ticks)
- "Click mini-bar → Tool Feed" navigation

**Difficulty**: Involved (4/10). Clarity 0, Solution 1 (canvas rendering for variable-height rows), Functional-Deps 1, Infra-Deps 0, Constraints 1.

### Phase 4: Tool Feed + Galaxy View Integration

Connect the pieces. Tool Feed gets richer context; Galaxy View gets aggregate signals.

- Tool Feed: add ToolPip to EventRow, agent name link, "Show in Timeline" action
- Galaxy View: tool family tint in session bar heat gradient
- Galaxy View: failure dot on session bars
- Galaxy View: ToolFamilyBar + ToolSummary in SessionDetail panel
- Cross-view navigation wiring (all the From→To links from the interaction model)
- Keyboard shortcuts (T, X, F)

**Difficulty**: Involved (4/10). Clarity 0, Solution 1, Functional-Deps 2 (depends on phases 1-3 and Galaxy View existing), Infra-Deps 0, Constraints 0.

---

## Data Requirements

No backend changes needed. All tool call data is already available:

- `GET /api/sessions/{id}/graph` returns Tool nodes and INVOKED edges with all properties
- `GET /api/sessions/{id}/timeline` returns `tool_events` array per agent
- SSE stream pushes PreToolUse/PostToolUse/PostToolUseFailure events in real-time
- `GET /api/events` supports filtering by tool_name, agent_id, session_id

The only new client-side computation is tool family classification (a pure function on tool name) and aggregate stats (counts, percentages, percentiles computed from the existing event data in the client stores).

---

## Open Questions

1. **ToolSearch, Skill, and future tools**: As Claude Code adds new tools, they need to be classified into families. The `meta` catch-all handles this gracefully — unknown tools default to meta. But we should review the classification periodically. Should the family mapping be configurable (a JSON file the user can edit) or hardcoded?

2. **Pip ring performance at scale**: An agent with 200+ tool calls will have a ring of 24 pips (capped). But if 10 agents each have pip rings, that's 240 extra DOM/canvas elements in the spawn tree. Need to profile. If it's a problem, pip rings could be progressive — only render for the selected agent and its immediate neighbors.

3. **Timeline canvas vs DOM**: The timeline currently renders everything on a single canvas. Expandable rows with clickable mini-bars might be better served by a hybrid approach — canvas for the base Gantt, DOM overlays for expanded rows. This is an implementation detail, but it affects the interaction model (canvas hit-testing vs native click events).

4. **Tool Feed virtualization**: The tool feed currently renders all filtered events in the DOM. Adding a ToolPip to each row is fine, but if we add cross-view navigation links (which require resolving agent/session context per row), we need to make sure the feed stays snappy at 10k+ events. The existing 10k ring buffer in the event store helps, but the filter/render path matters.
