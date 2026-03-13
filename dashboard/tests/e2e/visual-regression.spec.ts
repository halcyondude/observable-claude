import { test, expect } from '@playwright/test';
import { navigateAndSettle } from './helpers';

// ---------------------------------------------------------------------------
// Visual regression tests for all 7 dashboard views.
//
// Each test navigates to a view, waits for content to settle, and takes a
// full-page screenshot that Playwright diffs against a committed baseline.
//
// Run:       npm run test:visual
// Update:    ./scripts/update-baselines.sh
// ---------------------------------------------------------------------------

test.describe('Galaxy View', () => {
  test('default state', async ({ page }) => {
    await navigateAndSettle(page, '/');
    await expect(page).toHaveScreenshot('galaxy-view-default.png', { fullPage: true });
  });

  test('detail panel open', async ({ page }) => {
    await navigateAndSettle(page, '/');
    // Click the first session bar to open the detail panel
    const sessionBar = page.locator('[data-testid="session-bar"]').first();
    if (await sessionBar.isVisible()) {
      await sessionBar.click();
      await page.waitForTimeout(300);
    }
    await expect(page).toHaveScreenshot('galaxy-view-detail-panel.png', { fullPage: true });
  });

  test('time range changed', async ({ page }) => {
    await navigateAndSettle(page, '/');
    // Interact with the time brush if present
    const timeBrush = page.locator('[data-testid="time-brush"]');
    if (await timeBrush.isVisible()) {
      const box = await timeBrush.boundingBox();
      if (box) {
        // Drag from 25% to 75% of the brush width to narrow the range
        await page.mouse.move(box.x + box.width * 0.25, box.y + box.height / 2);
        await page.mouse.down();
        await page.mouse.move(box.x + box.width * 0.75, box.y + box.height / 2);
        await page.mouse.up();
        await page.waitForTimeout(300);
      }
    }
    await expect(page).toHaveScreenshot('galaxy-view-time-range.png', { fullPage: true });
  });
});

test.describe('Spawn Tree', () => {
  test('default state', async ({ page }) => {
    await navigateAndSettle(page, '/tree');
    await expect(page).toHaveScreenshot('spawn-tree-default.png', { fullPage: true });
  });

  test('node selected with detail panel', async ({ page }) => {
    await navigateAndSettle(page, '/tree');
    // Click the first tree node to select it
    const node = page.locator('[data-testid="tree-node"]').first();
    if (await node.isVisible()) {
      await node.click();
      await page.waitForTimeout(300);
    }
    await expect(page).toHaveScreenshot('spawn-tree-node-selected.png', { fullPage: true });
  });
});

test.describe('Timeline', () => {
  test('default state', async ({ page }) => {
    await navigateAndSettle(page, '/timeline');
    await expect(page).toHaveScreenshot('timeline-default.png', { fullPage: true });
  });

  test('agent row expanded with tool bars', async ({ page }) => {
    await navigateAndSettle(page, '/timeline');
    // Expand the first agent row
    const agentRow = page.locator('[data-testid="agent-row"]').first();
    if (await agentRow.isVisible()) {
      await agentRow.click();
      await page.waitForTimeout(300);
    }
    await expect(page).toHaveScreenshot('timeline-row-expanded.png', { fullPage: true });
  });
});

test.describe('Tool Feed', () => {
  test('default state', async ({ page }) => {
    await navigateAndSettle(page, '/tools');
    await expect(page).toHaveScreenshot('tool-feed-default.png', { fullPage: true });
  });

  test('event row expanded with JSON', async ({ page }) => {
    await navigateAndSettle(page, '/tools');
    // Expand the first tool event row
    const eventRow = page.locator('[data-testid="tool-event"]').first();
    if (await eventRow.isVisible()) {
      await eventRow.click();
      await page.waitForTimeout(300);
    }
    await expect(page).toHaveScreenshot('tool-feed-expanded.png', { fullPage: true });
  });
});

test.describe('Analytics', () => {
  test('default state', async ({ page }) => {
    await navigateAndSettle(page, '/analytics');
    await expect(page).toHaveScreenshot('analytics-default.png', { fullPage: true });
  });

  test('different time range selected', async ({ page }) => {
    await navigateAndSettle(page, '/analytics');
    // Click a time range selector if present (e.g., "7d", "30d" buttons)
    const rangeBtn = page.locator('[data-testid="time-range-btn"]').nth(1);
    if (await rangeBtn.isVisible()) {
      await rangeBtn.click();
      await page.waitForTimeout(300);
    }
    await expect(page).toHaveScreenshot('analytics-time-range.png', { fullPage: true });
  });
});

test.describe('Query Console', () => {
  test('NL tab', async ({ page }) => {
    await navigateAndSettle(page, '/query');
    await expect(page).toHaveScreenshot('query-nl-tab.png', { fullPage: true });
  });

  test('Cypher tab', async ({ page }) => {
    await navigateAndSettle(page, '/query');
    const cypherTab = page.locator('[data-testid="tab-cypher"]');
    if (await cypherTab.isVisible()) {
      await cypherTab.click();
      await page.waitForTimeout(300);
    }
    await expect(page).toHaveScreenshot('query-cypher-tab.png', { fullPage: true });
  });

  test('Messages tab', async ({ page }) => {
    await navigateAndSettle(page, '/query');
    const messagesTab = page.locator('[data-testid="tab-messages"]');
    if (await messagesTab.isVisible()) {
      await messagesTab.click();
      await page.waitForTimeout(300);
    }
    await expect(page).toHaveScreenshot('query-messages-tab.png', { fullPage: true });
  });
});

test.describe('Sessions', () => {
  test('default state', async ({ page }) => {
    await navigateAndSettle(page, '/sessions');
    await expect(page).toHaveScreenshot('sessions-default.png', { fullPage: true });
  });

  test('session selected with detail', async ({ page }) => {
    await navigateAndSettle(page, '/sessions');
    // Click the first session row to select it
    const sessionRow = page.locator('[data-testid="session-row"]').first();
    if (await sessionRow.isVisible()) {
      await sessionRow.click();
      await page.waitForTimeout(300);
    }
    await expect(page).toHaveScreenshot('sessions-selected.png', { fullPage: true });
  });
});
