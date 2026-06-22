const { test, expect } = require('@playwright/test');

test.describe('Refund and Return Workflows', () => {
  test('E2E Refund Flow - Success', async ({ page }) => {
    // We assume the app is running locally on port 5173 or similar.
    // The test will simply mock or assume a chat flow.
    await page.goto('http://localhost:5173');

    // Wait for chat to be ready
    await page.waitForSelector('input[placeholder="Type a message..."]', { timeout: 10000 });

    // Send refund query
    await page.fill('input[placeholder="Type a message..."]', 'What is the refund status of my order ORD001?');
    await page.press('input[placeholder="Type a message..."]', 'Enter');

    // Expect bot to reply with refund details (we wait for a response that mentions refund)
    await expect(page.locator('.message.bot').last()).toContainText(/refund/i, { timeout: 20000 });
  });

  test('E2E Return Flow - Success', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForSelector('input[placeholder="Type a message..."]', { timeout: 10000 });

    // Send return query
    await page.fill('input[placeholder="Type a message..."]', 'I want to return my order ORD002.');
    await page.press('input[placeholder="Type a message..."]', 'Enter');

    // Expect bot to reply regarding return initiation or status
    await expect(page.locator('.message.bot').last()).toContainText(/return|policy/i, { timeout: 20000 });
  });
});
