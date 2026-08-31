import { test, expect } from '@playwright/test'

test.describe('Landing page', () => {
  test('renders hero headline and CTA', async ({ page }) => {
    await page.goto('/')
    // The brand is written "TekWatch" in the document title and "Tek Watch" in
    // the product UI. Matching an optional space keeps this from failing on a
    // difference that has never mattered to anyone reading it.
    await expect(page).toHaveTitle(/Tek\s?Watch/i)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    // Primary CTA button is visible
    const cta = page.getByRole('link', { name: /demo|get started|dashboard/i }).first()
    await expect(cta).toBeVisible()
  })

  test('navigation links are reachable', async ({ page }) => {
    // This asserted that the body did not contain the text "500", meaning it to
    // stand for an HTTP 500 page. The landing copy sells a £500/month managed
    // tier and a 500-resource plan, so the assertion failed on the pricing
    // section — a passing build reported as broken, on every run, for a string
    // that was never evidence of an error.
    //
    // The response status is the thing actually worth checking, and the nav
    // links are what this test claims to be about.
    const response = await page.goto('/')
    expect(response?.status()).toBeLessThan(400)

    await expect(page.locator('body')).not.toContainText('Application error')

    const signIn = page.getByRole('link', { name: /sign in/i }).first()
    await expect(signIn).toBeVisible()
    const href = await signIn.getAttribute('href')
    expect(href).toBeTruthy()

    // Navigating directly rather than clicking: this is a static export, so a
    // click races the hydration that turns the anchor into a client-side route
    // and the assertion lands before navigation starts. Following the href
    // proves the destination is actually reachable, which is what the test is
    // named for, without depending on that timing.
    const destination = await page.goto(href!)
    expect(destination?.status()).toBeLessThan(400)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })
})
