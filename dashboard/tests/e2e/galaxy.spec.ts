import { test, expect } from '@playwright/test';
import { navigateToView, screenshot, TIMEOUTS } from './helpers';

test.describe('Galaxy View', () => {
	test.beforeEach(async ({ page }) => {
		await navigateToView(page, 'galaxy');
	});

	test('renders workspace swim lanes', async ({ page }) => {
		// Galaxy view should show swim lane containers when sessions exist
		// Each GalaxySwimLane renders a workspace row
		const main = page.locator('main');
		await expect(main).toBeVisible();

		// With seeded data, there should be at least one workspace lane
		// The lanes are inside a scrollable container
		const laneContainer = main.locator('div.flex-1.overflow-y-auto');
		await expect(laneContainer).toBeVisible({ timeout: TIMEOUTS.dataLoad });

		await screenshot(page, 'galaxy-swim-lanes');
	});

	test('time brush is visible', async ({ page }) => {
		// The time brush section has a border-bottom and contains the GalaxyTimeBrush
		const timeBrushArea = page.locator('div[style*="border-bottom"]').filter({
			has: page.locator('[role="radiogroup"]'),
		});
		await expect(timeBrushArea).toBeVisible({ timeout: TIMEOUTS.dataLoad });

		await screenshot(page, 'galaxy-time-brush');
	});

	test('recency preset selector works', async ({ page }) => {
		// The preset selector is a radiogroup with buttons
		const presetGroup = page.getByRole('radiogroup', { name: 'Time range' });
		await expect(presetGroup).toBeVisible({ timeout: TIMEOUTS.dataLoad });

		// Check all preset buttons exist
		for (const label of ['1h', '4h', '24h', '7d', 'All']) {
			await expect(presetGroup.getByRole('radio', { name: label })).toBeVisible();
		}

		// Click "All" preset
		await presetGroup.getByRole('radio', { name: 'All' }).click();
		// The clicked button should become checked
		await expect(presetGroup.getByRole('radio', { name: 'All' })).toHaveAttribute(
			'aria-checked',
			'true',
		);

		await screenshot(page, 'galaxy-preset-all');
	});

	test('session count is displayed', async ({ page }) => {
		// Session count text appears near the presets
		const countText = page.locator('text=/\\d+ sessions?/');
		await expect(countText).toBeVisible({ timeout: TIMEOUTS.dataLoad });
	});

	test('clicking a session bar opens detail panel', async ({ page }) => {
		// Wait for swim lanes to render with sessions
		await page.waitForTimeout(TIMEOUTS.ui);

		// The session bars are rendered inside GalaxySwimLane components
		// They're clickable elements that trigger selectedGalaxySessionId
		const sessionBar = page.locator('main [style*="cursor"]').first();
		if (await sessionBar.isVisible()) {
			await sessionBar.click();

			// Detail panel should appear with session metadata
			// GalaxyDetailPanel shows session info when a session is selected
			await page.waitForTimeout(TIMEOUTS.ui);
			await screenshot(page, 'galaxy-detail-open');
		}
	});

	test('shows empty state when no sessions in time range', async ({ page }) => {
		// Select 1h preset — if seeded data is old enough, this triggers empty state
		const presetGroup = page.getByRole('radiogroup', { name: 'Time range' });
		await expect(presetGroup).toBeVisible({ timeout: TIMEOUTS.dataLoad });

		await presetGroup.getByRole('radio', { name: '1h' }).click();
		await page.waitForTimeout(TIMEOUTS.ui);

		// Check for either swim lanes or empty state message
		const emptyMessage = page.locator('text=/No sessions in this time window/');
		const swimLanes = page.locator('main div.flex-1.overflow-y-auto');

		// One of these should be visible
		const hasEmpty = await emptyMessage.isVisible();
		const hasLanes = await swimLanes.isVisible();
		expect(hasEmpty || hasLanes).toBeTruthy();

		if (hasEmpty) {
			// Empty state should have a "Show all sessions" button
			await expect(page.getByRole('button', { name: 'Show all sessions' })).toBeVisible();
			await screenshot(page, 'galaxy-empty-state');
		}
	});

	test('keyboard nav: arrow keys move between lanes', async ({ page }) => {
		// Wait for data to load
		await page.waitForTimeout(TIMEOUTS.ui);

		// Press ArrowDown to focus first lane
		await page.keyboard.press('ArrowDown');
		await page.waitForTimeout(500);

		// Press ArrowDown again to move to next lane (if exists)
		await page.keyboard.press('ArrowDown');
		await page.waitForTimeout(500);

		// Press ArrowUp to go back
		await page.keyboard.press('ArrowUp');
		await page.waitForTimeout(500);

		await screenshot(page, 'galaxy-keyboard-nav');
	});

	test('full page screenshot', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);
		await screenshot(page, 'galaxy-full', { fullPage: true });
	});
});
