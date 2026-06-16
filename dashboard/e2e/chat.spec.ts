import { test, expect } from '@playwright/test'

test.describe('Chat / Ask AI page', () => {
  test('renders input and welcome state', async ({ page }) => {
    await page.goto('/chat')
    await expect(page.locator('body')).not.toContainText('Application error')

    // A textarea or input for the user message should be present
    const input = page.locator('textarea, input[type="text"]').first()
    await expect(input).toBeVisible()
  })

  test('typing in the chat input works', async ({ page }) => {
    await page.goto('/chat')
    const input = page.locator('textarea, input[type="text"]').first()
    await input.fill('How many EC2 instances are running?')
    await expect(input).toHaveValue('How many EC2 instances are running?')
  })
})
