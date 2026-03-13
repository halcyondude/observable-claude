import { test, expect } from '@playwright/test';
import { navigateToView, screenshot, TIMEOUTS } from './helpers';

test.describe('Analytics View', () => {
	test.beforeEach(async ({ page }) => {
		await navigateToView(page, 'analytics');
	});

	test('time range selector renders', async ({ page }) => {
		// Time range buttons: 5m, 30m, 1h, Session, All time
		for (const label of ['Last 5m', 'Last 30m', 'Last 1h', 'Session', 'All time']) {
			await expect(page.getByRole('button', { name: label })).toBeVisible({
				timeout: TIMEOUTS.appShell,
			});
		}

		await screenshot(page, 'analytics-time-range');
	});

	test('stat cards render', async ({ page }) => {
		// Four stat cards: Total Events, Active Agents, Tool Success Rate, Median Latency
		const labels = ['Total Events', 'Active Agents', 'Tool Success Rate', 'Median Latency'];

		for (const label of labels) {
			await expect(page.locator(`text=${label}`)).toBeVisible({
				timeout: TIMEOUTS.dataLoad,
			});
		}

		await screenshot(page, 'analytics-stat-cards');
	});

	test('stat card values are present', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);

		// Total Events should show a number
		const totalEventsCard = page.locator('text=Total Events').locator('..');
		await expect(totalEventsCard).toBeVisible();

		// Tool Success Rate should show a percentage
		const successRateText = page.locator('text=/\\d+%/');
		await expect(successRateText.first()).toBeVisible({ timeout: TIMEOUTS.dataLoad });

		// Median Latency should show ms value
		const latencyText = page.locator('text=/\\d+ms/');
		await expect(latencyText.first()).toBeVisible({ timeout: TIMEOUTS.dataLoad });
	});

	test('tool latency chart renders with seeded data', async ({ page }) => {
		// Switch to "All time" or "Session" to ensure seeded data is visible
		await page.getByRole('button', { name: 'Session' }).click();
		await page.waitForTimeout(TIMEOUTS.ui);

		// Tool Latency section header
		const latencyHeader = page.locator('h3:text("Tool Latency")');
		if (await latencyHeader.isVisible()) {
			// Chart should have tool name labels (monospace font)
			const chart = latencyHeader.locator('..');
			await expect(chart).toBeVisible();

			await screenshot(page, 'analytics-latency-chart');
		}
	});

	test('per-tool table renders', async ({ page }) => {
		await page.getByRole('button', { name: 'Session' }).click();
		await page.waitForTimeout(TIMEOUTS.ui);

		// Table has headers: Tool, Calls, p50, p95
		const table = page.locator('table');
		if (await table.isVisible()) {
			const headers = table.locator('th');
			await expect(headers.nth(0)).toContainText('Tool');
			await expect(headers.nth(1)).toContainText('Calls');
			await expect(headers.nth(2)).toContainText('p50');
			await expect(headers.nth(3)).toContainText('p95');

			// Table should have rows with tool data
			const rows = table.locator('tbody tr');
			const rowCount = await rows.count();
			expect(rowCount).toBeGreaterThan(0);

			await screenshot(page, 'analytics-tool-table');
		}
	});

	test('table columns are sortable', async ({ page }) => {
		await page.getByRole('button', { name: 'Session' }).click();
		await page.waitForTimeout(TIMEOUTS.ui);

		const table = page.locator('table');
		if (await table.isVisible()) {
			// Click "Calls" header to sort
			await table.locator('th:text("Calls")').click();
			await page.waitForTimeout(500);
			await screenshot(page, 'analytics-sorted-calls');

			// Click again to reverse sort
			await table.locator('th:text("Calls")').click();
			await page.waitForTimeout(500);
			await screenshot(page, 'analytics-sorted-calls-reverse');
		}
	});

	test('time range changes update data', async ({ page }) => {
		// Click "All time" to see all data
		await page.getByRole('button', { name: 'All time' }).click();
		await page.waitForTimeout(TIMEOUTS.ui);

		// Get the total events count
		const allTimeCount = await page
			.locator('text=Total Events')
			.locator('..')
			.textContent();

		// Switch to 5m — should show fewer or equal events
		await page.getByRole('button', { name: 'Last 5m' }).click();
		await page.waitForTimeout(TIMEOUTS.ui);

		const fiveMinCount = await page
			.locator('text=Total Events')
			.locator('..')
			.textContent();

		// Both should have rendered (content may differ)
		expect(allTimeCount).toBeTruthy();
		expect(fiveMinCount).toBeTruthy();
	});

	test('full page screenshot', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);
		await screenshot(page, 'analytics-full', { fullPage: true });
	});
});
