import { test, expect } from '@playwright/test'

test.describe('Landing page', () => {
  test('renders hero headline and CTA', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/Tek Watch/)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    // Primary CTA button is visible
    const cta = page.getByRole('link', { name: /demo|get started|dashboard/i }).first()
    await expect(cta).toBeVisible()
  })

  test('navigation links are reachable', async ({ page }) => {
    await page.goto('/')
    // The page should not show an error
    await expect(page.locator('body')).not.toContainText('Application error')
    await expect(page.locator('body')).not.toContainText('500')
  })
})
