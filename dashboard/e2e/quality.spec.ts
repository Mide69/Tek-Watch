import { test, expect } from '@playwright/test'

/**
 * Checks that are easy to break and easy to miss: in-page navigation, the
 * theme toggle, and the accessibility basics that make a form usable at all.
 */

test.describe('Landing page navigation', () => {
  test('the header anchors reach their sections', async ({ page }) => {
    await page.goto('/')

    for (const [label, id] of [['Platform', 'features'], ['How it works', 'how-it-works'], ['Pricing', 'pricing']]) {
      const target = page.locator(`#${id}`)
      await expect(target, `#${id} should exist for the "${label}" link`).toHaveCount(1)
    }
  })

  test('sign in and the demo are reachable from the header', async ({ page }) => {
    await page.goto('/')
    const hrefs = await page.locator('a').evaluateAll(as => as.map(a => a.getAttribute('href')))
    expect(hrefs).toContain('/login/')
    expect(hrefs.some(h => h?.includes('demo=1'))).toBe(true)
  })
})

test.describe('Theme', () => {
  test('the toggle switches the document theme and sticks', async ({ page }) => {
    await page.goto('/overview/?demo=1')

    const toggle = page.getByRole('button', { name: /light mode|dark mode/i }).first()
    await expect(toggle).toBeVisible()

    const isDark = () => page.evaluate(() => document.documentElement.classList.contains('dark'))

    // The theme is applied by an effect after hydration. Reading before it has
    // run gives "light" for a moment on a page that is about to be dark, which
    // made this flaky and told us nothing about the toggle.
    await expect.poll(isDark, { timeout: 5000 }).toBe(true)

    await toggle.click()
    await expect.poll(isDark, { timeout: 4000 }).toBe(false)

    // Persistence is the half a user actually notices.
    await page.reload()
    await expect.poll(isDark, { timeout: 5000 }).toBe(false)
  })
})

test.describe('Accessibility basics', () => {
  for (const path of ['/login', '/signup', '/contact']) {
    test(`${path} — every input is labelled`, async ({ page }) => {
      await page.goto(path)
      const unlabelled = await page.evaluate(() =>
        Array.from(document.querySelectorAll('input, select, textarea'))
          .filter(el => {
            const e = el as HTMLInputElement
            if (e.type === 'hidden') return false
            const id = e.getAttribute('id')
            const labelled =
              (id && document.querySelector(`label[for="${id}"]`)) ||
              e.getAttribute('aria-label') ||
              e.getAttribute('aria-labelledby') ||
              e.closest('label')
            return !labelled
          })
          .map(el => (el as HTMLInputElement).name || (el as HTMLInputElement).type),
      )
      expect(unlabelled, 'inputs with no accessible label').toEqual([])
    })
  }

  test('every button has an accessible name', async ({ page }) => {
    await page.goto('/overview/?demo=1')
    await page.waitForTimeout(1500)
    const nameless = await page.evaluate(() =>
      Array.from(document.querySelectorAll('button'))
        .filter(b => !(b.innerText.trim() || b.getAttribute('aria-label') || b.title))
        .map(b => b.className.toString().slice(0, 45)),
    )
    expect(nameless, 'buttons a screen reader cannot announce').toEqual([])
  })

  test('images carry alt text', async ({ page }) => {
    await page.goto('/')
    const noAlt = await page.evaluate(() =>
      Array.from(document.querySelectorAll('img'))
        .filter(i => i.getAttribute('alt') === null)
        .map(i => i.getAttribute('src')?.slice(0, 50) || '(no src)'),
    )
    expect(noAlt, 'images with no alt attribute').toEqual([])
  })
})
