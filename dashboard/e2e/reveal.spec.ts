import { test, expect } from '@playwright/test'

/**
 * Scroll-reveal content must actually become visible.
 *
 * The landing page hides everything below the fold at opacity 0 and reveals it
 * with an IntersectionObserver. That is a design where a single mistake — an
 * observer that never fires, an animation that does not fill forwards — leaves
 * real content permanently invisible while still present in the DOM, so it
 * passes every check that looks for text.
 *
 * Playwright's toBeVisible does not consider opacity, so this asserts the
 * computed value directly.
 */
test.describe('Landing page scroll reveals', () => {
  test('every revealed block ends up fully opaque', async ({ page }) => {
    await page.goto('/')

    const height = await page.evaluate(() => document.body.scrollHeight)
    for (let y = 0; y <= height; y += 400) {
      await page.evaluate(pos => window.scrollTo(0, pos), y)
      await page.waitForTimeout(120)
    }
    await page.evaluate(() => window.scrollTo(0, 0))
    // Longest reveal is 0.7s plus staggered delays.
    await page.waitForTimeout(2500)

    const faded = await page.evaluate(() => {
      const out: string[] = []
      for (const el of Array.from(document.querySelectorAll<HTMLElement>('*'))) {
        const r = el.getBoundingClientRect()
        if (r.height < 24) continue

        const s = getComputedStyle(el)
        // Decorative layers are meant to be faded: the background grid sits at
        // 0.6, and the hover glows are opacity-0 until pointed at. Neither
        // carries content, and both are pointer-events-none or explicitly
        // opacity-classed, so excluding them keeps this test about text people
        // are supposed to read.
        if (s.pointerEvents === 'none') continue
        if (/opacity-\d/.test(el.className.toString())) continue
        if (!el.innerText || !el.innerText.trim()) continue

        const op = parseFloat(s.opacity)
        if (op < 0.9) out.push(el.tagName + '.' + el.className.toString().slice(0, 50) + ' opacity=' + op)
      }
      return out
    })

    expect(faded, 'blocks left faded after scrolling the whole page').toEqual([])
  })
})
