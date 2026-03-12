# UI Testing & Self-Improvement Loop for Claude Code

> Claude Code can write frontend code but can't see what it renders. This closes the loop.

---

## The Problem

Claude Code operates in text. It generates Svelte components, CSS, layout logic — but has zero visual feedback. It can't tell if a component renders correctly, if the layout broke, or if a color is wrong. The dev cycle is: write code, hope it works, wait for a human to eyeball it. That's slow, and it doesn't scale.

What we need: Claude Code writes UI code, builds it, renders it in a real browser, sees the result, evaluates it, and fixes what's broken. A closed loop.

---

## 1. Browser MCP Servers — What Exists Today

### Microsoft Playwright MCP (the winner)

**Repo**: [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)

The official Playwright team ships an MCP server. It's the best option for CC Observer.

**What it does:**
- Launches a real browser (Chrome, Firefox, WebKit, Edge)
- Navigates to URLs (including `localhost:4242`)
- Takes screenshots (full page or element-level)
- Reads DOM via accessibility tree snapshots (2-5KB structured data, 10-100x faster than screenshot-based approaches)
- Clicks elements, fills forms, reads text content
- Executes JavaScript in the page
- 25+ tools exposed via MCP

**Setup for Claude Code:**
```bash
claude mcp add playwright -- npx @playwright/mcp@latest
```

That's it. One command. Persists in `~/.claude.json`.

**Key config flags:**
- `--browser chrome|firefox|webkit|msedge` — pick your engine
- `--caps vision,pdf` — enable screenshot/vision capabilities
- `--allowed-hosts localhost` — restrict to local dev

**Why this wins:** It's Microsoft-maintained, uses the accessibility tree (not fragile pixel coordinates), works with localhost, and Claude Code already supports MCP servers natively. No cloud service, no API keys, no latency.

### Puppeteer MCP

**Repo**: [@modelcontextprotocol/server-puppeteer](https://www.npmjs.com/package/@modelcontextprotocol/server-puppeteer)

Official MCP reference server. Does screenshots, DOM interaction, console monitoring, JavaScript execution. Works fine but Playwright MCP is more capable (cross-browser, accessibility tree, more tools). Puppeteer MCP is the fallback if Playwright MCP has issues.

### Cloud Browser Services (Browserbase, Browserless)

**Browserbase**: [mcp-server-browserbase](https://github.com/browserbase/mcp-server-browserbase) — Cloud headless browsers with Stagehand integration. Overkill for local dev. Makes sense if you need CI testing against a remote browser farm.

**Browserless**: [browserless-mcp](https://github.com/Lizzard-Solutions/browserless-mcp) — Similar, self-hostable via Docker. Interesting for CI but unnecessary for the local dev loop.

**Verdict**: Skip cloud browsers for now. Playwright MCP running locally against localhost:4242 is the right tool. Revisit cloud browsers if we need CI visual testing later.

---

## 2. Screenshot + Multimodal Vision — Claude Can See

This is the critical capability. Claude Code's Read tool handles image files. When you read a PNG, Claude sees it visually — it's a multimodal LLM.

**The workflow:**
1. Playwright MCP takes a screenshot → saves to `/tmp/screenshot.png`
2. Claude Code reads the PNG via the Read tool
3. Claude evaluates the visual output against expectations
4. Claude identifies issues (broken layout, missing elements, wrong colors)
5. Claude fixes the code and repeats

**What Claude can evaluate from screenshots:**
- Layout correctness (is the sidebar where it should be?)
- Component rendering (do all panels show up?)
- Color/theme consistency
- Data presence (are charts populated? are lists filled?)
- Responsive behavior (resize browser, screenshot, check)
- Error states (does the error boundary render cleanly?)

**What Claude struggles with:**
- Pixel-perfect comparison (use dedicated tools for that)
- Animation/transition quality (screenshots are static)
- Subtle color differences (within a few shades)
- Performance/jank (need metrics, not screenshots)

**Existing tools in this space:**
- [claude-code-frontend-dev](https://github.com/hemangjoshi37a/claude-code-frontend-dev) — multimodal visual testing plugin, closed-loop with Claude 4.5 Sonnet vision
- [claude-code-app-screenshot-tester](https://github.com/nathanwjclark/claude-code-app-screenshot-tester) — screenshots web apps during load for Claude to evaluate

---

## 3. Playwright Test Runner (Non-MCP) — Structured E2E

Independent of the MCP server. Standard `npx playwright test` workflow.

**For CC Observer:**
```bash
# Install
npm init playwright@latest

# Run tests
npx playwright test

# Run with screenshots on failure
npx playwright test --screenshot on

# Generate HTML report
npx playwright show-report
```

**Claude Code can:**
- Write Playwright test files
- Run them via Bash tool
- Read test results (pass/fail, error messages)
- Read failure screenshots
- Fix code, re-run, iterate

**SvelteKit integration**: SvelteKit scaffolds with Playwright support out of the box (`npm create svelte@latest` offers it as an option). Test files go in `/tests/`.

**Visual regression with Playwright:**
```typescript
// Pixel-diff comparison built into Playwright
await expect(page).toHaveScreenshot('galaxy-view.png');
```

First run creates the baseline. Subsequent runs diff against it. Failures produce a visual diff image. Claude can read these diffs.

---

## 4. Docker-Based Testing

The CC Observer dashboard runs in Docker (nginx serving static SvelteKit build on port 4242). Testing against the running stack is the most realistic option.

**Approach:**
1. `docker compose up -d` — start the full stack
2. Playwright (MCP or test runner) hits `localhost:4242`
3. Tests interact with the real collector, real DuckDB, real LadybugDB
4. Seed test data via `POST /events` to the collector

**Seeding test data:**
```bash
# Replay a captured session to populate the dashboard
python scripts/replay.py --input data/test-fixtures/sample-session.json

# Or POST synthetic events directly
curl -X POST localhost:4001/events \
  -H "Content-Type: application/json" \
  -d @data/test-fixtures/session-start.json
```

**Headless browser in Docker (for CI):**
```yaml
# Add to docker-compose.test.yml
services:
  playwright:
    image: mcr.microsoft.com/playwright:v1.50.0-noble
    depends_on:
      - dashboard
    volumes:
      - ./tests:/tests
      - ./test-results:/test-results
    command: npx playwright test --reporter=html
```

---

## 5. Component-Level Testing

### Storybook for SvelteKit

[Storybook](https://storybook.js.org/docs/get-started/frameworks/sveltekit) supports SvelteKit natively. It mirrors SvelteKit settings automatically — `$lib` aliases, `$app/environment`, `$app/stores`, `$app/paths` all work.

**What this gives us:**
- Isolated component rendering (test the Spawn Tree without the full dashboard)
- Stories as visual documentation
- Interaction tests via `play` functions
- Visual regression via [Chromatic](https://www.chromatic.com/) (free for open-ish projects)

**For CC Observer components:**
- Galaxy View swim lanes
- Spawn Tree with tool pip rings
- Timeline with colored ticks
- Conversation panel
- Replay controls
- Tool Feed entries

Each gets stories with different data states: empty, loading, populated, error, edge cases.

**Claude Code + Storybook workflow:**
1. Claude writes a component + its stories
2. `npm run storybook` serves stories on localhost:6006
3. Playwright MCP navigates to the story
4. Screenshot → evaluate → fix → repeat

### @testing-library/svelte + Vitest

For fast, non-visual component tests:
```bash
npm install -D @testing-library/svelte vitest
```

Tests DOM structure, event handling, reactive state — but no visual output. Complementary to screenshot-based testing, not a replacement.

### Vitest Browser Mode

The newer approach: Vitest renders components in a real browser (via Playwright provider) instead of jsdom. Closest to reality without going full E2E.

```typescript
// vitest.config.ts
export default defineConfig({
  test: {
    browser: {
      enabled: true,
      provider: 'playwright',
      name: 'chromium',
    },
  },
});
```

---

## 6. The Self-Improvement Loop — Full Architecture

Here's the closed loop for CC Observer. Every step is achievable with tools that exist today.

### Prerequisites

```bash
# One-time setup
claude mcp add playwright -- npx @playwright/mcp@latest
npm init playwright@latest  # in the dashboard directory
```

### The Loop

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  1. Claude writes/modifies UI code                  │
│     └─ Edit Svelte components, CSS, stores          │
│                                                     │
│  2. Build                                           │
│     └─ npm run build (SvelteKit static build)       │
│                                                     │
│  3. Start the stack                                 │
│     └─ docker compose up -d                         │
│                                                     │
│  4. Seed test data                                  │
│     └─ POST synthetic events to collector           │
│     └─ or run scripts/replay.py                     │
│                                                     │
│  5. Navigate browser (Playwright MCP)               │
│     └─ browser_navigate to localhost:4242            │
│                                                     │
│  6. Take screenshots                                │
│     └─ browser_screenshot → /tmp/cc-obs-*.png       │
│                                                     │
│  7. Read screenshots (Read tool, multimodal)        │
│     └─ Claude sees the rendered dashboard           │
│                                                     │
│  8. Evaluate against spec                           │
│     └─ Compare to design doc expectations           │
│     └─ Check layout, data, interactions             │
│                                                     │
│  9. Identify issues                                 │
│     └─ Layout bugs, missing elements, wrong colors  │
│                                                     │
│  10. Fix and repeat (back to step 1)                │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### What's Available Today vs. What's Missing

| Step | Tool | Available? | Notes |
|------|------|-----------|-------|
| Write code | Claude Code native | Yes | Core capability |
| Build | `npm run build` via Bash | Yes | Standard SvelteKit |
| Start stack | `docker compose up` via Bash | Yes | Already built |
| Seed data | `curl` / `replay.py` via Bash | Yes | Need test fixtures |
| Navigate browser | Playwright MCP `browser_navigate` | Yes | Works with localhost |
| Screenshot | Playwright MCP `browser_screenshot` | Yes | Full page or element |
| Read screenshot | Read tool (multimodal) | Yes | Claude sees PNGs |
| Evaluate visually | Claude's vision capability | Yes | Good for layout, structure |
| Click/interact | Playwright MCP `browser_click` | Yes | Via accessibility tree |
| Read DOM state | Playwright MCP `browser_snapshot` | Yes | Structured accessibility data |
| Pixel-diff regression | `toHaveScreenshot()` in Playwright tests | Yes | Need baseline images |
| Test SSE live updates | Playwright + wait for selector | Yes | Watch for DOM changes |

**Nothing is missing.** Every step in the loop is achievable with existing tools. The gap isn't tooling — it's wiring. We need to set it up, create test fixtures, and write the initial test suite.

---

## 7. E2E Test Strategy for CC Observer Dashboard

### The 7+ Dashboard Views to Test

| View | Key Elements | Test Focus |
|------|-------------|------------|
| **Galaxy View** | Swim lanes per workspace, time brush, session bars, sparklines | Layout, time range selection, session count |
| **Spawn Tree** | DAG of agents, tool pip rings, depth indicators | Tree structure, node expansion, tool coloring |
| **Timeline** | Horizontal time axis, colored ticks per tool family, expandable rows | Tick placement, color mapping, zoom behavior |
| **Conversation Panel** | Chat-style messages, user/assistant distinction | Message ordering, scroll behavior, search |
| **Tool Feed** | Chronological tool invocations, status badges | Live updates via SSE, filtering |
| **Session List** | Grouped by workspace, sortable, filterable | Grouping logic, sort order, empty states |
| **Replay Controls** | Play/pause/seek/speed, timeline scrubber | Playback state, speed control, seek accuracy |
| **Analytics** | Aggregate stats, charts | Data accuracy, chart rendering |
| **Query (NL→Cypher)** | Input box, results table, graph viz | Query execution, result display |

### Test Data Strategy

**Fixtures needed:**
1. **Minimal session**: 1 session, 1 agent, 3 tool calls — validates basic rendering
2. **Multi-agent session**: Nested subagents, parallel tool calls — validates spawn tree depth
3. **Multi-session workspace**: 5+ sessions in same cwd — validates Galaxy View grouping
4. **Long-running session**: 100+ tool calls — validates timeline scrolling, performance
5. **Error session**: Failed tool calls, stopped agents — validates error states
6. **Empty state**: No sessions at all — validates empty state UI

**Fixture format**: JSON arrays of hook events, replayable via `POST /events` or `scripts/replay.py`.

Store in `data/test-fixtures/`.

### SSE Testing

Real-time updates are the hardest to test. Approach:

```typescript
// Start with a loaded dashboard
await page.goto('http://localhost:4242');

// POST a new event to the collector
await fetch('http://localhost:4001/events', {
  method: 'POST',
  body: JSON.stringify(newToolCallEvent),
});

// Wait for the SSE-driven UI update
await expect(page.locator('.tool-feed-entry').last())
  .toContainText('Read', { timeout: 5000 });
```

This validates the full pipeline: hook event → collector → DuckDB → SSE → dashboard DOM update.

### Visual Regression Baseline

For each view, create golden screenshots:
```
tests/screenshots/
  galaxy-view-populated.png
  galaxy-view-empty.png
  spawn-tree-nested.png
  timeline-zoomed.png
  conversation-panel.png
  ...
```

Playwright's `toHaveScreenshot()` diffs against these automatically. Update baselines when design intentionally changes.

---

## 8. Implementation Order — What to Do First

### Phase 1: Wire the Loop (Day 1)

1. **Add Playwright MCP to the project**: `claude mcp add playwright -- npx @playwright/mcp@latest`
2. **Create a test fixture**: Capture a real session's events, save as `data/test-fixtures/minimal-session.json`
3. **Smoke test**: Claude navigates to localhost:4242, takes a screenshot, reads it. Prove the loop works.

### Phase 2: Structured E2E (Week 1)

4. **Install Playwright test runner** in the dashboard directory
5. **Write smoke tests** for each dashboard view: navigate, wait for content, screenshot, assert key elements
6. **Create test data seeding script**: loads fixtures, waits for SSE delivery, returns when ready
7. **Set up visual regression baselines** for each view

### Phase 3: Component Testing (Week 1-2)

8. **Add Storybook** with SvelteKit framework support
9. **Write stories** for the core atomic components (Tool Pip, session bar, time brush)
10. **Add Vitest browser mode** for fast component-level checks

### Phase 4: CI Integration (Week 2)

11. **Docker-based Playwright** in `docker-compose.test.yml`
12. **GitHub Actions workflow**: build → start stack → seed data → run Playwright tests → upload report
13. **Visual regression in CI**: baselines checked into git, diffs on PRs

### Phase 5: Self-Improvement Skill (Week 2-3)

14. **Create a Claude Code skill** (`/oc:visual-check`) that runs the full loop: build → start → seed → navigate → screenshot → evaluate → report issues
15. **Design spec as prompt input**: the skill reads a design spec file and evaluates screenshots against it
16. **Iteration protocol**: the skill can run in a loop, fixing and re-checking until all views pass

---

## Sources

- [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [Simon Willison: Playwright MCP with Claude Code](https://til.simonwillison.net/claude-code/playwright-mcp-claude-code)
- [Playwright MCP setup guide](https://www.builder.io/blog/playwright-mcp-server-claude-code)
- [Puppeteer MCP server](https://www.npmjs.com/package/@modelcontextprotocol/server-puppeteer)
- [Browserbase MCP](https://github.com/browserbase/mcp-server-browserbase)
- [Claude Code Frontend Dev plugin](https://github.com/hemangjoshi37a/claude-code-frontend-dev)
- [Round-trip screenshot testing](https://medium.com/@rotbart/giving-claude-code-eyes-round-trip-screenshot-testing-ce52f7dcc563)
- [Claude Code visual feedback for Electron](https://juri.dev/articles/visual-feedback-loop-electron-apps-claude-code/)
- [Self-improving coding agents (Addy Osmani)](https://addyosmani.com/blog/self-improving-agents/)
- [Storybook for SvelteKit](https://storybook.js.org/docs/get-started/frameworks/sveltekit)
- [SvelteKit testing docs](https://svelte.dev/docs/svelte/testing)
- [Playwright visual comparisons](https://playwright.dev/docs/test-snapshots)
- [Vitest browser mode with Svelte](https://scottspence.com/posts/testing-with-vitest-browser-svelte-guide)
- [Kitbook visual regression testing](https://kitbook.vercel.app/docs/7-visual-regression-testing)
- [Claude Code feature request: native browser integration](https://github.com/anthropics/claude-code/issues/10646)
