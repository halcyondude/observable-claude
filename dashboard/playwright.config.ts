import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: './tests/e2e',
	use: {
		baseURL: 'http://localhost:4242',
		screenshot: 'only-on-failure',
	},
	webServer: undefined, // managed externally via Docker
});
