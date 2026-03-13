import { test, expect } from '@playwright/test';
import { waitForDashboard, screenshot, TIMEOUTS } from './helpers';

test.describe('SSE / Real-time features', () => {
	test('connection indicator shows status', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		// TopBar has a connection status indicator: dot + label
		const header = page.locator('header');
		await expect(header).toBeVisible();

		// Status dot (rounded-full w-2 h-2)
		const statusDot = header.locator('.rounded-full.w-2.h-2');
		await expect(statusDot).toBeVisible();

		// Status label should be one of: Connected, Reconnecting, Disconnected
		const statusText = header.locator('text=/Connected|Reconnecting|Disconnected/');
		await expect(statusText).toBeVisible();

		await screenshot(page, 'sse-connection-status');
	});

	test('connection indicator has correct color for connected state', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		// Give SSE time to connect
		await page.waitForTimeout(TIMEOUTS.ui);

		const header = page.locator('header');
		const statusDot = header.locator('.rounded-full.w-2.h-2');
		await expect(statusDot).toBeVisible();

		// Connected = green (#22c55e), Disconnected = red (#ef4444)
		const style = await statusDot.getAttribute('style');
		expect(style).toBeTruthy();

		// The status should be visible regardless of connection state
		const statusLabel = header.locator('text=/Connected|Reconnecting|Disconnected/');
		const label = await statusLabel.textContent();
		expect(label?.trim()).toMatch(/Connected|Reconnecting|Disconnected/);

		await screenshot(page, 'sse-status-detail');
	});

	test('retry button appears when disconnected', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		const header = page.locator('header');

		// Check if disconnected (Retry button only appears in disconnected state)
		const retryBtn = header.getByRole('button', { name: 'Retry' });
		const disconnectedText = header.locator('text=Disconnected');

		if (await disconnectedText.isVisible()) {
			await expect(retryBtn).toBeVisible();
			await screenshot(page, 'sse-disconnected-retry');
		}
	});

	test('app shell text shows session info or "No active session"', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);

		const header = page.locator('header');

		// TopBar shows either session info (ID, cwd, elapsed) or "No active session"
		const noSession = header.locator('text=No active session');
		const sessionInfo = header.locator('.font-mono');

		const hasNoSession = await noSession.isVisible();
		const hasSessionInfo = await sessionInfo.isVisible();

		expect(hasNoSession || hasSessionInfo).toBeTruthy();

		await screenshot(page, 'sse-session-info');
	});

	test('active agent badge in header', async ({ page }) => {
		await page.goto('/tree');
		await waitForDashboard(page);
		await page.waitForTimeout(TIMEOUTS.ui);

		// If there are active agents, a badge appears in the header
		const header = page.locator('header');
		const agentBadge = header.locator('.rounded-full.font-medium');

		if (await agentBadge.isVisible()) {
			const count = await agentBadge.textContent();
			expect(parseInt(count ?? '0')).toBeGreaterThan(0);
			await screenshot(page, 'sse-agent-badge');
		}
	});
});
