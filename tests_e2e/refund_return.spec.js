const { test, expect } = require('@playwright/test');

test.describe('Refund and Return Workflows', () => {
  const targetUrl = process.env.PLAYWRIGHT_TEST_URL || 'https://my-agentic-lab.web.app';

  test('E2E Refund Flow - Success', async ({ page }) => {
    // We assume the app is running locally on port 5173 or similar.
    // The test will simply mock or assume a chat flow.
    await page.goto(targetUrl);

    // Wait for chat to be ready
    await page.waitForSelector('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', { timeout: 10000 });

    // Send refund query
    await page.fill('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', 'What is the refund status of my order ORD001?');
    await page.press('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', 'Enter');

    // Wait for bot response
    // Ensure the response comes from the bot
    const botMessages = page.locator('.message.bot');
    await expect(botMessages).toHaveCount(2, { timeout: 20000 });
  });

  test('E2E Return Flow - Success', async ({ page }) => {
    await page.goto(targetUrl);
    await page.waitForSelector('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', { timeout: 10000 });

    // Send return query
    await page.fill('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', 'I want to return my order ORD002.');
    await page.press('input[placeholder*="Ask"], textarea[placeholder*="Ask"]', 'Enter');

    // Wait for bot response
    // Ensure the response comes from the bot
    const botMessages = page.locator('.message.bot');
    await expect(botMessages).toHaveCount(2, { timeout: 20000 });
  });
});
