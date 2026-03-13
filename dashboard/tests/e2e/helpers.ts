import { type Page, expect } from '@playwright/test';

/** Standard timeouts for different wait scenarios */
export const TIMEOUTS = {
	/** Wait for app shell to load (sidebar, topbar) */
	appShell: 10_000,
	/** Wait for data-dependent content to render */
	dataLoad: 15_000,
	/** Wait for Cytoscape canvas or other heavy renders */
	canvas: 20_000,
	/** Wait for detail panel animations */
	panel: 3_000,
	/** Short waits for UI state changes */
	ui: 2_000,
};

/** View paths and their names */
export const VIEWS = {
	galaxy: { path: '/galaxy', name: 'Galaxy' },
	tree: { path: '/tree', name: 'Spawn Tree' },
	timeline: { path: '/timeline', name: 'Timeline' },
	tools: { path: '/tools', name: 'Tool Feed' },
	analytics: { path: '/analytics', name: 'Analytics' },
	query: { path: '/query', name: 'Query' },
	sessions: { path: '/sessions', name: 'Sessions' },
} as const;

export type ViewKey = keyof typeof VIEWS;

/**
 * Wait for the dashboard app shell to load (sidebar + topbar + main content area).
 */
export async function waitForDashboard(page: Page): Promise<void> {
	await expect(page.locator('nav')).toBeVisible({ timeout: TIMEOUTS.appShell });
	await expect(page.locator('header')).toBeVisible({ timeout: TIMEOUTS.appShell });
	await expect(page.locator('main')).toBeVisible({ timeout: TIMEOUTS.appShell });
}

/**
 * Navigate to a view and wait for it to load.
 * Verifies the app shell is present and the main content area has rendered.
 */
export async function navigateToView(page: Page, view: ViewKey): Promise<void> {
	const { path } = VIEWS[view];
	await page.goto(path);
	await waitForDashboard(page);

	// Wait for main content area to have some content
	const main = page.locator('main');
	await expect(main).toBeVisible({ timeout: TIMEOUTS.appShell });
}

/**
 * Click an element and wait for a detail panel to appear.
 * Detail panels are fixed-position side panels (width: 320px) or bottom sheets.
 */
export async function openDetailPanel(
	page: Page,
	triggerSelector: string,
): Promise<void> {
	await page.locator(triggerSelector).first().click();
	// NodeDetail and GalaxyDetailPanel are both fixed/absolute positioned panels
	// with a close button (&times;)
	await page.locator('[class*="fixed"], [class*="absolute"]')
		.filter({ hasText: /\u00d7|Agent ID|Status/ })
		.first()
		.waitFor({ state: 'visible', timeout: TIMEOUTS.panel });
}

/**
 * Take a screenshot and save it to the standard screenshots directory.
 */
export async function screenshot(
	page: Page,
	name: string,
	options?: { fullPage?: boolean },
): Promise<void> {
	await page.screenshot({
		path: `tests/e2e/screenshots/${name}.png`,
		fullPage: options?.fullPage ?? true,
	});
}

/**
 * Get the connection status indicator dot color.
 */
export async function getConnectionStatus(page: Page): Promise<string> {
	const dot = page.locator('header .rounded-full').first();
	await expect(dot).toBeVisible({ timeout: TIMEOUTS.appShell });
	const bg = await dot.evaluate((el) => getComputedStyle(el).backgroundColor);
	return bg;
}

/**
 * Check that the sidebar has expected nav items.
 */
export async function verifySidebarNav(page: Page): Promise<void> {
	const nav = page.locator('nav');
	await expect(nav).toBeVisible({ timeout: TIMEOUTS.appShell });

	for (const view of Object.values(VIEWS)) {
		await expect(nav.getByRole('link', { name: view.name })).toBeVisible();
	}
}
