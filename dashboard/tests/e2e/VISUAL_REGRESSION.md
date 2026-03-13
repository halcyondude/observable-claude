# Visual Regression Testing

Playwright's built-in `toHaveScreenshot()` captures screenshots on the first run to create baselines, then diffs subsequent runs against those baselines. If the diff exceeds the configured threshold, the test fails and produces a visual diff image showing exactly what changed.

## Running Tests

```bash
# Run all visual regression tests
npm run test:visual

# Run via playwright directly (with grep filter)
npx playwright test visual-regression

# Run a specific view's tests
npx playwright test visual-regression -g "Galaxy View"
```

## Updating Baselines

After intentional UI changes, baselines need to be regenerated:

```bash
# Update all baselines
./scripts/update-baselines.sh

# Update baselines for a specific view
./scripts/update-baselines.sh "Galaxy View"
```

Review the updated screenshots in `tests/e2e/screenshots/` before committing. The diff images Playwright produces on failure (in `test-results/`) are particularly useful for verifying that only the intended areas changed.

## Threshold Configuration

The thresholds are set in `playwright.config.ts`:

- **`maxDiffPixelRatio: 0.01`** — Up to 1% of pixels can differ before the test fails. This catches layout breaks and missing elements while tolerating minor anti-aliasing differences across runs.
- **`threshold: 0.2`** — Per-pixel color distance threshold (0-1 scale). At 0.2, subtle color shifts from anti-aliasing are tolerated but a wrong background color or missing element will fail.
- **`animations: 'disabled'`** — CSS animations are force-stopped before capture, eliminating a major source of flaky diffs.

These values are tuned for "catches layout breaks, ignores rendering noise." If you find tests are too flaky, increase `maxDiffPixelRatio`. If they miss real regressions, decrease it.

## Platform-Specific Rendering

Fonts, anti-aliasing, and subpixel rendering differ between macOS, Linux, and Windows. Baselines generated on one platform will likely fail on another.

**Strategies:**

1. **Single-platform baselines (recommended for CI):** Generate baselines in the same environment that CI uses (e.g., the Playwright Docker image `mcr.microsoft.com/playwright:v1.50.0-noble`). This is the most deterministic approach.

2. **Per-platform baselines:** Playwright supports platform-specific snapshot names. Add to the config:
   ```typescript
   snapshotPathTemplate: '{testDir}/screenshots/{platform}/{testFilePath}/{testName}/{arg}{ext}',
   ```
   Then commit separate baselines for each OS.

3. **Local-only baselines (current approach):** Don't commit baselines. Each developer generates their own via `update-baselines.sh`. The `.gitignore` entry for `tests/e2e/screenshots/` supports this. Good for catching regressions during development; not suitable for CI enforcement.

## Troubleshooting

**Tests fail on first run:** Expected. The first run creates baselines. Run again to compare against them.

**Tests fail after pulling new code:** Someone changed the UI. Run `./scripts/update-baselines.sh`, review the new baselines, and commit them if they look correct.

**Tests flaky across runs (no code changes):** Usually caused by animations, dynamic timestamps, or data loading races. The test helpers disable animations and wait for network idle, but if a specific view has dynamic content (e.g., relative timestamps like "2 minutes ago"), consider masking that element:

```typescript
await expect(page).toHaveScreenshot('view.png', {
  mask: [page.locator('.relative-timestamp')],
});
```

**Diff images location:** When a test fails, Playwright writes three images to `test-results/`:
- `*-expected.png` — the baseline
- `*-actual.png` — what was rendered
- `*-diff.png` — highlighted pixel differences
