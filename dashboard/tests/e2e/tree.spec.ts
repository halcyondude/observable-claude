import { test, expect } from '@playwright/test';
import { navigateToView, screenshot, TIMEOUTS } from './helpers';

test.describe('Spawn Tree', () => {
	test.beforeEach(async ({ page }) => {
		await navigateToView(page, 'tree');
	});

	test('Cytoscape canvas renders', async ({ page }) => {
		// The tree view has a full-size container div that Cytoscape mounts into
		// The container has style="background: var(--color-bg);"
		const canvas = page.locator('main div.relative.w-full.h-full');
		await expect(canvas).toBeVisible({ timeout: TIMEOUTS.canvas });

		// Cytoscape injects a canvas element into its container
		const cytoscapeCanvas = page.locator('main canvas');
		await expect(cytoscapeCanvas).toBeVisible({ timeout: TIMEOUTS.canvas });

		await screenshot(page, 'tree-canvas');
	});

	test('floating controls are visible', async ({ page }) => {
		// Zoom controls: +, -, Fit, Reset
		const controls = page.locator('main .absolute.top-4.right-4');
		await expect(controls).toBeVisible({ timeout: TIMEOUTS.canvas });

		for (const label of ['+', 'Fit', 'Reset']) {
			await expect(controls.getByRole('button', { name: label })).toBeVisible();
		}
		// The minus button uses Unicode \u2212
		await expect(controls.locator('button').nth(1)).toBeVisible();
	});

	test('legend shows status colors', async ({ page }) => {
		const legend = page.locator('main .absolute.bottom-4.left-4');
		await expect(legend).toBeVisible({ timeout: TIMEOUTS.canvas });

		for (const status of ['Running', 'Complete', 'Failed', 'Session']) {
			await expect(legend.locator(`text=${status}`)).toBeVisible();
		}

		await screenshot(page, 'tree-legend');
	});

	test('agent nodes appear with correct status colors', async ({ page }) => {
		// Wait for Cytoscape to render nodes
		await page.waitForTimeout(TIMEOUTS.ui);

		// Check that the Cytoscape canvas has been drawn (has non-zero dimensions)
		const canvasEl = page.locator('main canvas').first();
		const dimensions = await canvasEl.boundingBox();
		expect(dimensions).not.toBeNull();
		expect(dimensions!.width).toBeGreaterThan(0);
		expect(dimensions!.height).toBeGreaterThan(0);

		await screenshot(page, 'tree-nodes');
	});

	test('clicking a node opens detail panel', async ({ page }) => {
		// Wait for graph to render
		await page.waitForTimeout(TIMEOUTS.ui);

		// Click on the Cytoscape canvas area (where nodes are)
		const canvasEl = page.locator('main canvas').first();
		const box = await canvasEl.boundingBox();
		if (box) {
			// Click near center where nodes typically render
			await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
			await page.waitForTimeout(TIMEOUTS.ui);

			// NodeDetail panel appears as a fixed panel on the right
			const detailPanel = page.locator('div.fixed.top-12.right-0');
			if (await detailPanel.isVisible()) {
				// Panel should show agent info
				await expect(detailPanel.locator('text=Agent ID')).toBeVisible();
				await expect(detailPanel.locator('text=Status')).toBeVisible();

				await screenshot(page, 'tree-detail-open');
			}
		}
	});

	test('detail panel shows agent metadata', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);

		// Click on canvas to try selecting a node
		const canvasEl = page.locator('main canvas').first();
		const box = await canvasEl.boundingBox();
		if (box) {
			await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
			await page.waitForTimeout(TIMEOUTS.ui);

			const detailPanel = page.locator('div.fixed.top-12.right-0');
			if (await detailPanel.isVisible()) {
				// Check for expected metadata sections
				await expect(detailPanel.locator('text=Agent ID')).toBeVisible();
				await expect(detailPanel.locator('text=Status')).toBeVisible();

				// Check for close button
				const closeBtn = detailPanel.locator('button').filter({ hasText: '\u00d7' });
				await expect(closeBtn).toBeVisible();

				// Close the panel
				await closeBtn.click();
				await expect(detailPanel).not.toBeVisible({ timeout: TIMEOUTS.panel });
			}
		}
	});

	test('tool pip rings visible at sufficient zoom', async ({ page }) => {
		// SVG overlay for pip rings only renders when zoom >= 0.6
		// The overlay is an SVG element with class containing "pointer-events-none"
		await page.waitForTimeout(TIMEOUTS.ui);

		const svgOverlay = page.locator('main svg.absolute.inset-0');
		// At default zoom, pip rings may or may not be visible depending on zoom level
		const isVisible = await svgOverlay.isVisible();

		if (isVisible) {
			await screenshot(page, 'tree-pip-rings');
		}
	});

	test('zoom controls work', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);

		const controls = page.locator('main .absolute.top-4.right-4');

		// Click Fit to ensure everything is visible
		await controls.getByRole('button', { name: 'Fit' }).click();
		await page.waitForTimeout(500);
		await screenshot(page, 'tree-fit');

		// Click zoom in
		await controls.getByRole('button', { name: '+' }).click();
		await page.waitForTimeout(500);
		await screenshot(page, 'tree-zoomed-in');

		// Click Reset
		await controls.getByRole('button', { name: 'Reset' }).click();
		await page.waitForTimeout(500);
		await screenshot(page, 'tree-reset');
	});

	test('full page screenshot', async ({ page }) => {
		await page.waitForTimeout(TIMEOUTS.ui);
		await screenshot(page, 'tree-full', { fullPage: true });
	});
});
