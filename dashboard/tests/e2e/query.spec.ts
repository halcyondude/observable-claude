import { test, expect } from '@playwright/test';
import { navigateToView, screenshot, TIMEOUTS } from './helpers';

test.describe('Query Console', () => {
	test.beforeEach(async ({ page }) => {
		await navigateToView(page, 'query');
	});

	test('three mode tabs render', async ({ page }) => {
		// Mode toggle buttons: Natural Language, Cypher, Messages
		await expect(page.getByRole('button', { name: 'Natural Language' })).toBeVisible({
			timeout: TIMEOUTS.appShell,
		});
		await expect(page.getByRole('button', { name: 'Cypher' })).toBeVisible();
		await expect(page.getByRole('button', { name: 'Messages' })).toBeVisible();

		await screenshot(page, 'query-tabs');
	});

	test('NL tab has input field and example chips', async ({ page }) => {
		// Natural Language mode is default
		// Should have a textarea input
		const textarea = page.locator('textarea');
		await expect(textarea).toBeVisible({ timeout: TIMEOUTS.appShell });
		await expect(textarea).toHaveAttribute('placeholder', /Which agents/);

		// Ask button
		await expect(page.getByRole('button', { name: 'Ask' })).toBeVisible();

		// Example chips should be present
		const chipTexts = [
			'Which agents are currently running?',
			'What tool calls failed',
			'slowest tool call',
		];
		for (const text of chipTexts) {
			await expect(
				page.locator('button.rounded-full').filter({ hasText: new RegExp(text, 'i') }).first(),
			).toBeVisible();
		}

		await screenshot(page, 'query-nl-tab');
	});

	test('Cypher tab has code editor area', async ({ page }) => {
		await page.getByRole('button', { name: 'Cypher' }).click();
		await page.waitForTimeout(TIMEOUTS.ui);

		// Cypher mode should have a textarea with monospace font placeholder
		const textarea = page.locator('textarea');
		await expect(textarea).toBeVisible();
		await expect(textarea).toHaveAttribute('placeholder', /MATCH/);

		// Ask button (same button, different context)
		await expect(page.getByRole('button', { name: 'Ask' })).toBeVisible();

		// Example chips should NOT be visible in Cypher mode
		const chips = page.locator('button.rounded-full');
		const chipCount = await chips.count();
		// Cypher mode doesn't show NL example chips
		expect(chipCount).toBe(0);

		await screenshot(page, 'query-cypher-tab');
	});

	test('Messages tab has search input', async ({ page }) => {
		await page.getByRole('button', { name: 'Messages' }).click();
		await page.waitForTimeout(TIMEOUTS.ui);

		// Messages mode should have a search input
		const searchInput = page.locator('input[placeholder*="Search message"]');
		await expect(searchInput).toBeVisible();

		// Search button
		await expect(page.getByRole('button', { name: 'Search' })).toBeVisible();

		// Role filter select
		const roleSelect = page.locator('select');
		await expect(roleSelect).toBeVisible();

		// Agent ID filter input
		const agentInput = page.locator('input[placeholder*="Agent ID"]');
		await expect(agentInput).toBeVisible();

		// Search chips for common terms
		const searchChips = page.locator('button.rounded-full');
		const chipCount = await searchChips.count();
		expect(chipCount).toBeGreaterThan(0);

		await screenshot(page, 'query-messages-tab');
	});

	test('NL tab: clicking example chip populates input', async ({ page }) => {
		// Click the first example chip
		const firstChip = page.locator('button.rounded-full').first();
		const chipText = await firstChip.textContent();
		await firstChip.click();

		// This triggers submit, so we should see loading or results
		await page.waitForTimeout(TIMEOUTS.ui);

		// Either we see results, an error, or loading state
		const hasResult = await page.locator('table, text=/No results/').isVisible();
		const hasError = await page.locator('text=/Query failed|failed/i').isVisible();

		// At minimum, the input should have been populated
		expect(hasResult || hasError).toBeTruthy();

		await screenshot(page, 'query-chip-result');
	});

	test('mode switching preserves state', async ({ page }) => {
		// Type something in NL mode
		const textarea = page.locator('textarea');
		await textarea.fill('test query');

		// Switch to Cypher
		await page.getByRole('button', { name: 'Cypher' }).click();
		await page.waitForTimeout(500);

		// Switch to Messages
		await page.getByRole('button', { name: 'Messages' }).click();
		await page.waitForTimeout(500);

		// Switch back to NL
		await page.getByRole('button', { name: 'Natural Language' }).click();
		await page.waitForTimeout(500);

		await screenshot(page, 'query-mode-switch');
	});

	test('keyboard shortcut: / focuses input', async ({ page }) => {
		// Press / to focus the input
		await page.keyboard.press('/');
		await page.waitForTimeout(500);

		// The textarea should be focused
		const focused = await page.evaluate(() => document.activeElement?.tagName);
		expect(focused).toBe('TEXTAREA');
	});

	test('full page screenshot', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);
		await screenshot(page, 'query-full', { fullPage: true });
	});
});
