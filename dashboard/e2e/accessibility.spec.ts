import { test, expect } from '@playwright/test'

// Spot-check aria-labels on key interactive elements added in the recent audit fix.

test.describe('Accessibility — aria-labels on interactive elements', () => {
  test('overview page: header controls have aria-labels', async ({ page }) => {
    await page.goto('/overview')

    // These were specifically added in the accessibility fix commit
    await expect(page.getByRole('button', { name: /refresh/i })).toBeAttached()
    await expect(page.getByRole('combobox', { name: /region/i })).toBeAttached()
  })

  test('mobile viewport: hamburger menu has an accessible name', async ({ page }) => {
    // "Open navigation" is lg:hidden — only in the accessibility tree below the lg breakpoint
    await page.setViewportSize({ width: 480, height: 800 })
    await page.goto('/overview')
    await expect(page.getByRole('button', { name: /open navigation/i })).toBeVisible()
  })

  test('theme toggle has accessible label', async ({ page }) => {
    await page.goto('/overview')
    const toggle = page.getByRole('button', { name: /switch to (light|dark) mode/i })
    await expect(toggle).toBeVisible()
  })

  test('notification bell has accessible label', async ({ page }) => {
    await page.goto('/overview')
    // NotificationBell renders as a <Link> (role="link"), not a <button>
    const bell = page.getByRole('link', { name: /alerts/i }).first()
    await expect(bell).toBeAttached()
  })

  test('no elements with role=button are missing accessible names', async ({ page }) => {
    await page.goto('/overview')
    // Find all buttons and check none have empty accessible names
    // (filters out buttons that Playwright can't detect a name for)
    const buttons = await page.getByRole('button').all()
    for (const btn of buttons) {
      const name = await btn.getAttribute('aria-label')
        ?? await btn.innerText()
      // Should have SOME accessible name
      expect(name?.trim().length, `Button has no accessible name`).toBeGreaterThan(0)
    }
  })
})
