---
name: oc:visual-check
description: Visual QA check of the CC Observer dashboard
---

Run an autonomous visual quality check of the CC Observer dashboard:

1. **Verify stack is running**: Check `GET http://localhost:4001/health`. If down, start it with `bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh` and wait for healthy.

2. **Seed test data if needed**: Check event count from health endpoint. If zero, run `python ${CLAUDE_PLUGIN_ROOT}/scripts/seed_test_data.py` to populate with test fixtures.

3. **Visual inspection of each view**: Use the Playwright MCP tools to:
   - Navigate to `http://localhost:4242`
   - For each view (Galaxy, Spawn Tree, Timeline, Tool Feed, Analytics, Query Console, Sessions):
     a. Navigate to the view's route
     b. Wait for content to load (2s)
     c. Take a screenshot
     d. Read the screenshot using the Read tool (multimodal)
     e. Evaluate against the design spec in `${CLAUDE_PLUGIN_ROOT}/docs/ux.md`:
        - Are the correct elements present? (sidebar, top bar, main content)
        - Are colors correct? (dark navy background, teal accents, proper status colors)
        - Is the layout correct? (sidebar width, content area, panels)
        - Are there any visual bugs? (overflow, clipping, misalignment, missing elements)
        - Is text readable? (contrast, font sizes)

4. **Test key interactions**:
   - Click an agent node in Spawn Tree — verify detail panel opens
   - Click a session in Galaxy View — verify detail panel opens
   - Expand a tool row in Timeline — verify expansion works

5. **Generate report**: Output a structured report:
   - For each view: PASS/WARN/FAIL with specific findings
   - Screenshots of any issues found
   - Suggested fixes with file paths and line numbers
   - Overall verdict

6. **Optional auto-fix**: If the user appended "fix" to the command (e.g., `/oc:visual-check fix`), attempt to fix identified issues and re-check.

**Fallback**: If Playwright MCP tools are not available, run `bash ${CLAUDE_PLUGIN_ROOT}/scripts/visual-check.sh` to capture screenshots via the Playwright test runner, then evaluate the saved screenshots manually using the Read tool.

Load the `visual-check` skill for design system reference when evaluating screenshots.
