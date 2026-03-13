import { test, expect } from '@playwright/test';
import { waitForDashboard, navigateToView, screenshot, TIMEOUTS, VIEWS } from './helpers';

test.describe('Cross-view navigation', () => {
	test('sidebar links navigate to all views', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		const nav = page.locator('nav');

		for (const [key, view] of Object.entries(VIEWS)) {
			await nav.getByRole('link', { name: view.name }).click();
			await page.waitForURL(`**${view.path}*`, { timeout: TIMEOUTS.appShell });
			await expect(page.locator('main')).toBeVisible();
		}

		await screenshot(page, 'navigation-sidebar-tour');
	});

	test('root path redirects to spawn tree', async ({ page }) => {
		await page.goto('/');
		// Root page redirects to /tree via onMount goto
		await page.waitForURL('**/tree*', { timeout: TIMEOUTS.appShell });
		await waitForDashboard(page);
	});

	test('keyboard shortcut Cmd+0 goes to Galaxy', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		await page.keyboard.press('Meta+0');
		await page.waitForURL('**/galaxy*', { timeout: TIMEOUTS.appShell });
	});

	test('keyboard shortcut Cmd+1 goes to Spawn Tree', async ({ page }) => {
		await page.goto('/galaxy');
		await waitForDashboard(page);

		await page.keyboard.press('Meta+1');
		await page.waitForURL('**/tree*', { timeout: TIMEOUTS.appShell });
	});

	test('keyboard shortcut Cmd+2 goes to Timeline', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		await page.keyboard.press('Meta+2');
		await page.waitForURL('**/timeline*', { timeout: TIMEOUTS.appShell });
	});

	test('keyboard shortcut Cmd+3 goes to Tool Feed', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		await page.keyboard.press('Meta+3');
		await page.waitForURL('**/tools*', { timeout: TIMEOUTS.appShell });
	});

	test('keyboard shortcut Cmd+4 goes to Analytics', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		await page.keyboard.press('Meta+4');
		await page.waitForURL('**/analytics*', { timeout: TIMEOUTS.appShell });
	});

	test('keyboard shortcut Cmd+5 goes to Query', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		await page.keyboard.press('Meta+5');
		await page.waitForURL('**/query*', { timeout: TIMEOUTS.appShell });
	});

	test('keyboard shortcut Cmd+6 goes to Sessions', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		await page.keyboard.press('Meta+6');
		await page.waitForURL('**/sessions*', { timeout: TIMEOUTS.appShell });
	});

	test('F key navigates to Tool Feed', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		// F key opens Tool Feed (when not in an input)
		await page.keyboard.press('f');
		await page.waitForURL('**/tools*', { timeout: TIMEOUTS.appShell });
	});

	test('tool feed agent filter via URL param', async ({ page }) => {
		const testAgentId = 'agent-00000000-0000-0000-0000-000000000001';
		await page.goto(`/tools?agent=${testAgentId}`);
		await waitForDashboard(page);

		// Agent filter badge should be visible
		const agentBadge = page.locator('button').filter({ hasText: /Agent:/ });
		if (await agentBadge.isVisible()) {
			await screenshot(page, 'navigation-agent-filter');
		}
	});

	test('Escape key closes detail panels', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);
		await page.waitForTimeout(TIMEOUTS.ui);

		// Try to open a node detail by clicking on the canvas
		const canvas = page.locator('main canvas').first();
		const box = await canvas.boundingBox();
		if (box) {
			await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
			await page.waitForTimeout(TIMEOUTS.ui);

			const panel = page.locator('div.fixed.top-12.right-0');
			if (await panel.isVisible()) {
				await page.keyboard.press('Escape');
				await expect(panel).not.toBeVisible({ timeout: TIMEOUTS.panel });
			}
		}
	});

	test('active sidebar item is highlighted', async ({ page }) => {
		await page.goto('/analytics');
		await waitForDashboard(page);

		// The active nav link has a visual indicator (primary color border-left)
		const activeLink = page.locator('nav a').filter({ hasText: 'Analytics' });
		await expect(activeLink).toBeVisible();

		// Check it has the active styles (background with primary color opacity)
		const bgStyle = await activeLink.getAttribute('style');
		expect(bgStyle).toContain('rgba(10, 147, 150');

		await screenshot(page, 'navigation-active-highlight');
	});
});
