import { type Page } from '@playwright/test';

/**
 * Base URL for the collector API.
 */
export const COLLECTOR_URL = process.env.COLLECTOR_URL || 'http://localhost:4001';

/**
 * Wait for the dashboard to finish loading — nav is visible and no spinners remain.
 */
export async function waitForDashboardReady(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
  // Wait for the nav/sidebar to be present (layout is rendered)
  await page.locator('nav').first().waitFor({ state: 'visible', timeout: 10_000 });
}

/**
 * Disable CSS animations and transitions for deterministic screenshots.
 */
export async function disableAnimations(page: Page): Promise<void> {
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
      }
    `,
  });
}

/**
 * Navigate to a dashboard view, wait for it to settle, and disable animations.
 */
export async function navigateAndSettle(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await waitForDashboardReady(page);
  await disableAnimations(page);
  // Extra settle time for any deferred rendering (charts, graphs)
  await page.waitForTimeout(500);
}

/**
 * Seed test events by POSTing to the collector.
 */
export async function seedEvents(events: Record<string, unknown>[]): Promise<void> {
  for (const event of events) {
    await fetch(`${COLLECTOR_URL}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
    });
  }
}
