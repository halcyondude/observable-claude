---
name: visual-check
description: Design system knowledge for visual QA evaluation of the CC Observer dashboard
---

# Visual QA — Design System Reference

Use this reference when evaluating dashboard screenshots against the design spec.

## Color Palette

| Token | Hex | Usage |
|---|---|---|
| Background | `#0D1B2A` | Navy — app background |
| Surface | `#1E293B` | Dark gray — cards, panels, sidebars |
| Surface 2 | `#2D3E50` | Inputs, code blocks, hover states |
| Primary | `#0A9396` | Teal — active, running, links |
| Success | `#94D2BD` | Mint — completed |
| Warning | `#EE9B00` | Amber — medium latency |
| Error | `#CA6702` | Coral — failed |
| Text | `#F4F8FB` | Near-white — primary text |
| Text muted | `#64748B` | Gray — secondary labels |
| Border | `#1E3A4A` | Subtle borders |

## Tool Family Colors

| Token | Hex | Family | Tools |
|---|---|---|---|
| `--tool-file` | `#7EB8DA` | File ops | Read, Write, Edit, Glob, Grep |
| `--tool-exec` | `#B8A9E8` | Execution | Bash |
| `--tool-agent` | `#0A9396` | Orchestration | Agent (reuses primary) |
| `--tool-mcp` | `#E8A87C` | External services | mcp__* |
| `--tool-meta` | `#94D2BD` | Internal bookkeeping | TodoRead, TodoWrite, TaskCreate, etc. |

## Typography

| Element | Font / Size / Weight |
|---|---|
| Display | Inter 24px Bold |
| Label | Inter 14px Medium |
| Body | Inter 13px Regular |
| Caption | Inter 11px Regular |
| Code | JetBrains Mono 12px |
| Monospace data | JetBrains Mono 13px |

## Layout

| Element | Dimension |
|---|---|
| Top bar | 48px height |
| Sidebar expanded | 200px width |
| Sidebar collapsed | 56px width (icon only) |
| Detail panel | 320px width |
| Event row collapsed | 48px height |
| Gantt row | 32px height, 4px gap |

## Status Encoding

| State | Fill | Text | Animation |
|---|---|---|---|
| Running | Teal `#0A9396` | White | Pulsing 2s border |
| Complete | Dark gray `#1E293B` | Muted | None (faded) |
| Failed | Coral `#CA6702` | White | Brief flash, then static |
| Connected | Green dot | — | Top bar only |
| Disconnected | Red dot | — | Top bar only |

## What to Check

When evaluating each screenshot, verify:

1. **Dark theme applied** — no white backgrounds anywhere. Background should be navy `#0D1B2A`.
2. **Sidebar navigation** — present, highlights active view with teal left border. 200px wide (or 56px collapsed below 960px).
3. **Top bar** — 48px, shows CC Observer wordmark, connection status pill, active session info.
4. **Content area** — fills available space between sidebar and any detail panel.
5. **Status colors** — running=teal, complete=gray, failed=coral. No mismatches.
6. **Tool family colors** — file=steel blue, exec=lavender, agent=teal, mcp=peach, meta=mint.
7. **Text readability** — near-white text on dark backgrounds. Muted gray for secondary. Sufficient contrast.
8. **Interactive elements** — hover states visible, clickable elements have cursor changes.
9. **No horizontal scrolling** — content should not overflow horizontally.
10. **Loading/empty states** — proper skeleton or message, not blank white space or broken layouts.
11. **Font rendering** — Inter for UI text, JetBrains Mono for code/IDs.

## View-Specific Checks

### Galaxy View (`/galaxy`)
- Time brush at top (64px, uPlot sparkline)
- Workspace swim lanes with session bars
- Session bars colored by status (teal=active, gray=complete, coral border=failed)
- Detail panel slides in on click (320px)

### Spawn Tree (`/spawn-tree`)
- Cytoscape.js DAG, top-to-bottom dagre layout
- Node sizes proportional to tool call count
- Directed edges with teal arrows
- Floating controls (zoom in/out/fit/reset)
- Floating legend

### Timeline (`/timeline`)
- Left column 200px with agent labels, indented by depth
- Horizontal Gantt bars on shared time axis
- Tool markers as 2px ticks on bars
- Current time as teal vertical line

### Tool Feed (`/tool-feed`)
- Reverse-chronological event rows (48px collapsed)
- 4px colored left border per event type
- Filter bar with event type pills
- Expanded rows show JSON with syntax highlighting

### Analytics (`/analytics`)
- 2x2 stat card grid (responsive)
- Tool latency horizontal bar chart
- Event rate stacked area chart
- Per-tool sortable table

### Query Console (`/query`)
- Natural language input with example chips
- Toggle between NL and Cypher modes
- Results as table or graph visualization
- Query history (last 20)

### Session History (`/sessions`)
- Left panel (320px) with session list
- Status dots: green=active, gray=complete
- Active session has teal border + LIVE badge
- Clicking switches all views to that session
