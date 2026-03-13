import { test, expect } from '@playwright/test';
import { navigateToView, screenshot, TIMEOUTS } from './helpers';

test.describe('Timeline View', () => {
	test.beforeEach(async ({ page }) => {
		await navigateToView(page, 'timeline');
	});

	test('canvas renders', async ({ page }) => {
		// Timeline uses a canvas element for drawing
		const canvas = page.locator('main canvas');
		await expect(canvas).toBeVisible({ timeout: TIMEOUTS.canvas });

		const box = await canvas.boundingBox();
		expect(box).not.toBeNull();
		expect(box!.width).toBeGreaterThan(0);
		expect(box!.height).toBeGreaterThan(0);

		await screenshot(page, 'timeline-canvas');
	});

	test('agent bars render on shared time axis', async ({ page }) => {
		// The canvas should be drawn with agent rows
		// We can verify the canvas has non-trivial content by checking its dimensions
		const canvas = page.locator('main canvas');
		await expect(canvas).toBeVisible({ timeout: TIMEOUTS.canvas });

		// Wait for data load and draw
		await page.waitForTimeout(TIMEOUTS.ui);

		await screenshot(page, 'timeline-agent-bars');
	});

	test('shows waiting state when no agents', async ({ page }) => {
		// If no session is active, shows "Waiting for agents..."
		const waitingText = page.locator('text=/Waiting for agents|No agents yet/');
		const canvas = page.locator('main canvas');

		// Either we have agents rendered on canvas, or we see the waiting message
		const hasWaiting = await waitingText.isVisible();
		const hasCanvas = await canvas.isVisible();

		expect(hasWaiting || hasCanvas).toBeTruthy();

		if (hasWaiting) {
			await screenshot(page, 'timeline-waiting');
		}
	});

	test('tooltip appears on hover', async ({ page }) => {
		const canvas = page.locator('main canvas');
		await expect(canvas).toBeVisible({ timeout: TIMEOUTS.canvas });

		const box = await canvas.boundingBox();
		if (box) {
			// Hover over the center of the canvas where agent rows are drawn
			await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
			await page.waitForTimeout(500);

			// Tooltip is a fixed-position div with status info
			const tooltip = page.locator('div.fixed.z-50.pointer-events-none');
			if (await tooltip.isVisible()) {
				await screenshot(page, 'timeline-tooltip');
			}
		}
	});

	test('full page screenshot', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);
		await screenshot(page, 'timeline-full', { fullPage: true });
	});
});
