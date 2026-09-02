import { defineConfig, devices } from '@playwright/test'

/**
 * Mirrors the dashboard's configuration. The admin console had no browser
 * coverage at all, which is the wrong place to have none: it manages every
 * customer on the platform, and a page that crashes or a form that cannot be
 * read is discovered by whoever is on support at the time.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  timeout: 45_000,
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:3001',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    navigationTimeout: 45_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    // No -s flag: this is a multi-page static export, one index.html per route.
    command: process.env.CI ? 'npx serve out -p 3001' : 'npm run dev -- -p 3001',
    url: 'http://localhost:3001',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
