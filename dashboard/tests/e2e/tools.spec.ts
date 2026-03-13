import { test, expect } from '@playwright/test';
import { navigateToView, screenshot, TIMEOUTS } from './helpers';

test.describe('Tool Feed', () => {
	test.beforeEach(async ({ page }) => {
		await navigateToView(page, 'tools');
	});

	test('filter bar renders with controls', async ({ page }) => {
		// Filter bar has type toggle buttons, tool name input, status select
		const filterBar = page.locator('div.flex.items-center.gap-3.px-4.py-2');
		await expect(filterBar).toBeVisible({ timeout: TIMEOUTS.appShell });

		// Event type filter buttons
		for (const label of ['PRE', 'POST', 'FAIL']) {
			await expect(filterBar.getByRole('button', { name: label })).toBeVisible();
		}

		// Tool name filter input
		await expect(filterBar.locator('input[placeholder*="Filter tool"]')).toBeVisible();

		// Status select
		await expect(filterBar.locator('select')).toBeVisible();

		// Pause button
		await expect(filterBar.getByRole('button', { name: /Pause|Resume/ })).toBeVisible();

		// Event count
		await expect(filterBar.locator('text=/\\d+ events/')).toBeVisible();

		await screenshot(page, 'tools-filter-bar');
	});

	test('event rows render with tool info', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);

		// Events are rendered as EventRow components in a scrollable container
		const eventList = page.locator('main div.flex-1.overflow-y-auto');
		await expect(eventList).toBeVisible({ timeout: TIMEOUTS.dataLoad });

		// Check for event content or empty state
		const hasEvents = await page.locator('text=/\\d+ events/').textContent();
		const count = parseInt(hasEvents?.match(/\d+/)?.[0] ?? '0');

		if (count > 0) {
			// Events should be visible in the list
			const firstEvent = eventList.locator('> div > div').first();
			await expect(firstEvent).toBeVisible();
			await screenshot(page, 'tools-events');
		} else {
			await expect(page.locator('text=No tool events yet')).toBeVisible();
			await screenshot(page, 'tools-empty');
		}
	});

	test('clicking an event row expands it', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);

		const eventList = page.locator('main div.flex-1.overflow-y-auto');
		const firstEvent = eventList.locator('> div > div').first();

		if (await firstEvent.isVisible()) {
			await firstEvent.click();
			await page.waitForTimeout(TIMEOUTS.ui);

			// Expanded state shows JSON detail (pre element or code block)
			await screenshot(page, 'tools-event-expanded');
		}
	});

	test('filter by event type works', async ({ page }) => {
		const filterBar = page.locator('div.flex.items-center.gap-3.px-4.py-2');

		// Click FAIL filter button
		await filterBar.getByRole('button', { name: 'FAIL' }).click();
		await page.waitForTimeout(TIMEOUTS.ui);

		// Event count should update
		await expect(filterBar.locator('text=/\\d+ events/')).toBeVisible();

		await screenshot(page, 'tools-filtered-fail');

		// Click again to deselect
		await filterBar.getByRole('button', { name: 'FAIL' }).click();
		await page.waitForTimeout(TIMEOUTS.ui);
	});

	test('filter by status works', async ({ page }) => {
		const filterBar = page.locator('div.flex.items-center.gap-3.px-4.py-2');
		const select = filterBar.locator('select');

		// Select "Failure" status
		await select.selectOption('failure');
		await page.waitForTimeout(TIMEOUTS.ui);

		await screenshot(page, 'tools-filtered-failure-status');

		// Reset to "All"
		await select.selectOption('all');
	});

	test('filter by agent via URL param', async ({ page }) => {
		// Navigate with agent filter in URL
		const testAgentId = 'agent-00000000-0000-0000-0000-000000000001';
		await page.goto(`/tools?agent=${testAgentId}`);
		await page.waitForTimeout(TIMEOUTS.ui);

		// Agent filter badge should appear in the filter bar
		const agentBadge = page.locator('button').filter({
			hasText: /Agent:/,
		});

		if (await agentBadge.isVisible()) {
			await screenshot(page, 'tools-filtered-agent');

			// Click the X to clear the agent filter
			await agentBadge.click();
			await page.waitForTimeout(TIMEOUTS.ui);
			await expect(agentBadge).not.toBeVisible();
		}
	});

	test('pause and resume works', async ({ page }) => {
		const filterBar = page.locator('div.flex.items-center.gap-3.px-4.py-2');
		const pauseBtn = filterBar.getByRole('button', { name: 'Pause' });

		if (await pauseBtn.isVisible()) {
			await pauseBtn.click();
			await expect(filterBar.getByRole('button', { name: 'Resume' })).toBeVisible();

			await screenshot(page, 'tools-paused');

			// Resume
			await filterBar.getByRole('button', { name: 'Resume' }).click();
			await expect(filterBar.getByRole('button', { name: 'Pause' })).toBeVisible();
		}
	});

	test('full page screenshot', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);
		await screenshot(page, 'tools-full', { fullPage: true });
	});
});
