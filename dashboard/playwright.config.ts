import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  // The Next.js dev server compiles pages on demand — concurrent first-visits
  // to heavy pages can abort each other's connections. Single worker avoids
  // that locally. In CI we serve the static export (`out/`), which has no
  // on-demand compile step, but we keep workers:1 for stable, easy-to-read logs.
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  timeout: 45_000,
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    navigationTimeout: 45_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // Local dev: run against `next dev` for fast iteration.
  // CI: app deploys as a static export (next.config.js `output: 'export'`) —
  // serve the actual built `out/` directory so tests exercise the real artifact
  // and avoid dev-server compile-on-demand flakiness entirely.
  webServer: {
    // NOTE: no `-s` (SPA) flag — this is a multi-page static export, each
    // route has its own out/<route>/index.html. `-s` rewrites every request
    // to the root index.html, which would silently serve the landing page
    // for every route.
    command: process.env.CI ? 'npx serve out -p 3000' : 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
