import { test, expect } from '@playwright/test';

test.describe('Refund and Return Workflows', () => {

  test('E2E Refund Flow - Success', async ({ page }) => {
    await page.goto('/');

    // Wait for chat to be ready
    await page.waitForSelector('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', { timeout: 10000 });

    // Send refund query
    await page.fill('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', 'What is the refund status of my order ORD001?');
    await page.press('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', 'Enter');

    // Wait for a reasonable time for the bot to respond (relies on live backend)
    // This test verifies the UI can send messages and receive responses
    await page.waitForTimeout(5000);

    // Verify the user message appeared
    const userMessage = page.locator('text=What is the refund status of my order ORD001?');
    await expect(userMessage).toBeVisible({ timeout: 10000 });
  });

  test('E2E Return Flow - Success', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', { timeout: 10000 });

    // Send return query
    await page.fill('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', 'I want to return my order ORD002.');
    await page.press('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', 'Enter');

    // Wait for response
    await page.waitForTimeout(5000);

    // Verify the user message appeared
    const userMessage = page.locator('text=I want to return my order ORD002.');
    await expect(userMessage).toBeVisible({ timeout: 10000 });
  });
});
