import { test, expect } from '@playwright/test';
import { navigateToView, screenshot, TIMEOUTS } from './helpers';

test.describe('Session History', () => {
	test.beforeEach(async ({ page }) => {
		await navigateToView(page, 'sessions');
	});

	test('session list panel renders', async ({ page }) => {
		// Left panel with session list (width: 320px, border-right)
		const sessionList = page.locator('main div.overflow-y-auto.border-r');
		await expect(sessionList).toBeVisible({ timeout: TIMEOUTS.dataLoad });

		await screenshot(page, 'sessions-list');
	});

	test('sessions show cwd and timestamps', async ({ page }) => {
		const sessionList = page.locator('main div.overflow-y-auto.border-r');
		await expect(sessionList).toBeVisible({ timeout: TIMEOUTS.dataLoad });

		// Each session button has cwd, timestamps, agent/event counts
		const firstSession = sessionList.locator('button').first();

		if (await firstSession.isVisible()) {
			// Should show the last path segment as title
			const title = firstSession.locator('.text-sm.font-semibold');
			await expect(title).toBeVisible();

			// Should show full cwd path
			const cwdText = firstSession.locator('.truncate');
			await expect(cwdText).toBeVisible();

			// Should show agent and event counts
			await expect(firstSession.locator('text=/\\d+ agents/')).toBeVisible();
			await expect(firstSession.locator('text=/\\d+ events/')).toBeVisible();

			await screenshot(page, 'sessions-entry-detail');
		}
	});

	test('clicking a session shows detail', async ({ page }) => {
		const sessionList = page.locator('main div.overflow-y-auto.border-r');
		const firstSession = sessionList.locator('button').first();

		if (await firstSession.isVisible()) {
			await firstSession.click();
			await page.waitForTimeout(TIMEOUTS.ui);

			// Right panel should show session detail
			const detailPanel = page.locator('main div.flex-1.flex.items-center');
			await expect(detailPanel).toBeVisible();

			// Detail shows session ID in monospace
			const sessionIdEl = detailPanel.locator('.font-mono');
			await expect(sessionIdEl).toBeVisible();

			// Detail shows agent count, event count, duration
			await expect(detailPanel.locator('text=agents')).toBeVisible();
			await expect(detailPanel.locator('text=events')).toBeVisible();
			await expect(detailPanel.locator('text=duration')).toBeVisible();

			await screenshot(page, 'sessions-detail');
		}
	});

	test('active sessions show status indicator', async ({ page }) => {
		const sessionList = page.locator('main div.overflow-y-auto.border-r');
		await expect(sessionList).toBeVisible({ timeout: TIMEOUTS.dataLoad });

		// Each session has a status dot (rounded-full w-2 h-2)
		const statusDots = sessionList.locator('.rounded-full.w-2.h-2');
		if ((await statusDots.count()) > 0) {
			await expect(statusDots.first()).toBeVisible();
		}
	});

	test('empty state when no sessions', async ({ page }) => {
		// If no sessions are loaded, should show empty message
		const emptyMessage = page.locator('text=No sessions found');
		const sessionButtons = page.locator('main div.overflow-y-auto.border-r button');

		const hasEmpty = await emptyMessage.isVisible();
		const hasSessions = (await sessionButtons.count()) > 0;

		// One of these states should be true
		expect(hasEmpty || hasSessions).toBeTruthy();

		if (hasEmpty) {
			await screenshot(page, 'sessions-empty');
		}
	});

	test('unselected state shows prompt', async ({ page }) => {
		// Before selecting any session, right panel shows "Select a session"
		const prompt = page.locator('text=Select a session to view details');
		if (await prompt.isVisible()) {
			await screenshot(page, 'sessions-unselected');
		}
	});

	test('full page screenshot', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);
		await screenshot(page, 'sessions-full', { fullPage: true });
	});
});
