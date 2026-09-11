import { test, expect } from '@playwright/test'

// All dashboard pages run in demo mode when Cognito isn't configured.
// Tests verify: correct HTTP status, no crash overlay, key structural elements visible.

const DASHBOARD_PAGES = [
  { path: '/overview',   heading: /overview/i   },
  { path: '/compute',    heading: /compute/i     },
  { path: '/databases',  heading: /database/i    },
  { path: '/networking', heading: /network/i     },
  { path: '/storage',    heading: /storage/i     },
  { path: '/messaging',  heading: /message|queue|sns|sqs/i },
  { path: '/security',   heading: /security/i    },
  { path: '/cost',       heading: /cost/i        },
  { path: '/alerts',     heading: /alert/i       },
  { path: '/agent',      heading: /agent/i       },
  { path: '/settings',   heading: /company profile/i },
]

test.describe('Dashboard pages (demo mode)', () => {
  for (const { path, heading } of DASHBOARD_PAGES) {
    test(`${path} — renders without crashing`, async ({ page }) => {
      await page.goto(path)

      // Page must not be a 500 or application error overlay
      await expect(page.locator('body')).not.toContainText('Application error')
      await expect(page.locator('body')).not.toContainText('DashboardProvider')

      // Navigation must be reachable. The sidebar is desktop only: below lg it
      // lives behind the hamburger, so at phone width that button is what has
      // to be there. Asserting the sidebar at every width failed all eleven
      // pages on a phone while the app was behaving correctly.
      const viewport = page.viewportSize()
      if (viewport && viewport.width < 1024) {
        await expect(page.getByRole('button', { name: /open navigation/i })).toBeVisible()
      } else {
        await expect(page.getByRole('navigation')).toBeVisible()
      }

      // At least one heading matching the page topic is visible
      await expect(
        page.getByRole('heading').filter({ hasText: heading }).first()
      ).toBeVisible({ timeout: 10_000 })
    })
  }

  test('sidebar navigation links route correctly', async ({ page }) => {
    await page.goto('/overview')

    // Below lg the sidebar is a drawer, so open it before clicking through.
    const hamburger = page.getByRole('button', { name: /open navigation/i })
    if (await hamburger.isVisible()) {
      await hamburger.click()
      await expect(page.getByRole('navigation')).toBeVisible()
    }

    // Click the "Cost" nav link and verify we land on /cost
    await page.getByRole('link', { name: /cost/i }).first().click()
    await expect(page).toHaveURL(/\/cost/)
    await expect(page.locator('body')).not.toContainText('Application error')
  })

  test('time range picker changes selection', async ({ page }) => {
    await page.goto('/overview')
    // Find a time range button that's not currently active and click it
    const btn = page.getByRole('button', { name: /^7d$/i })
    await btn.click()
    await expect(btn).toHaveClass(/bg-primary/)
  })

  test('region picker is interactive', async ({ page }) => {
    await page.goto('/overview')
    const select = page.getByRole('combobox', { name: /region/i })
    await expect(select).toBeVisible()
    await select.selectOption('eu-west-1')
    await expect(select).toHaveValue('eu-west-1')
  })

  test('refresh button is labelled and clickable', async ({ page }) => {
    await page.goto('/overview')
    const refreshBtn = page.getByRole('button', { name: /refresh/i })
    await expect(refreshBtn).toBeVisible()
    await refreshBtn.click()
    // No crash after refresh
    await expect(page.locator('body')).not.toContainText('Application error')
  })
})
