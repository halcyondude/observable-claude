import { test, expect } from '@playwright/test';

test.describe('Dashboard smoke tests', () => {
	test('homepage loads with app shell', async ({ page }) => {
		await page.goto('/');
		// Verify the app shell renders — layout has a sidebar and main content area
		await expect(page.locator('main')).toBeVisible();
		await page.screenshot({ path: 'test-results/screenshots/home.png', fullPage: true });
	});

	const views = [
		{ path: '/tree', name: 'Spawn Tree' },
		{ path: '/timeline', name: 'Timeline' },
		{ path: '/tools', name: 'Tools' },
		{ path: '/analytics', name: 'Analytics' },
		{ path: '/query', name: 'Query' },
		{ path: '/sessions', name: 'Sessions' },
	];

	for (const view of views) {
		test(`${view.name} view loads at ${view.path}`, async ({ page }) => {
			await page.goto(view.path);
			// Verify main content area is present and not empty
			const main = page.locator('main');
			await expect(main).toBeVisible();
			// Page should have some content (not a blank error page)
			const content = await main.textContent();
			expect(content?.trim().length).toBeGreaterThan(0);
			await page.screenshot({
				path: `test-results/screenshots${view.path}.png`,
				fullPage: true,
			});
		});
	}
});
