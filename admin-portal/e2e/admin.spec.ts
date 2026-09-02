import { test, expect } from '@playwright/test'

/**
 * The admin console manages every customer on the platform, and until now had
 * no browser coverage whatsoever. These are the checks that would have caught
 * the faults already found on the customer dashboard: a page that crashes on
 * an empty response, a form nothing can read, a control with no name.
 *
 * Runs against the demo build, which is what CI produces without secrets.
 */

const PAGES = ['/dashboard', '/customers', '/thresholds', '/operations']

test.describe('Admin pages', () => {
  for (const path of PAGES) {
    test(`${path} renders without crashing`, async ({ page }) => {
      const errors: string[] = []
      page.on('pageerror', e => errors.push(e.message))

      const res = await page.goto(path)
      expect(res?.status(), `${path} should be served`).toBeLessThan(400)
      await page.waitForTimeout(1200)

      await expect(page.locator('body')).not.toContainText('Something went wrong')
      await expect(page.locator('body')).not.toContainText('Application error')
      expect(errors, `uncaught errors on ${path}`).toEqual([])
    })
  }
})

test.describe('Admin sign-in', () => {
  test('every field is labelled', async ({ page }) => {
    await page.goto('/login')
    const unlabelled = await page.evaluate(() =>
      Array.from(document.querySelectorAll('input, select, textarea'))
        .filter(el => {
          const e = el as HTMLInputElement
          if (e.type === 'hidden') return false
          const id = e.getAttribute('id')
          return !(
            (id && document.querySelector(`label[for="${id}"]`)) ||
            e.getAttribute('aria-label') ||
            e.getAttribute('aria-labelledby') ||
            e.closest('label')
          )
        })
        .map(el => (el as HTMLInputElement).name || (el as HTMLInputElement).type),
    )
    expect(unlabelled, 'inputs with no accessible label').toEqual([])
  })

  test('refuses empty credentials rather than signing anyone in', async ({ page }) => {
    await page.goto('/login')
    const submit = page.getByRole('button', { name: /continue|sign in/i }).first()
    await submit.click()
    await page.waitForTimeout(800)
    // Still on the login page: an empty form must never open the console.
    await expect(page).toHaveURL(/login/)
  })
})

test.describe('Admin accessibility basics', () => {
  test('every button has an accessible name', async ({ page }) => {
    await page.goto('/customers')
    await page.waitForTimeout(1500)
    const nameless = await page.evaluate(() =>
      Array.from(document.querySelectorAll('button'))
        .filter(b => !(b.innerText.trim() || b.getAttribute('aria-label') || b.title))
        .map(b => b.className.toString().slice(0, 45)),
    )
    expect(nameless, 'buttons a screen reader cannot announce').toEqual([])
  })
})
