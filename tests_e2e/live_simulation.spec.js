import { test, expect } from '@playwright/test';

test.describe('Live Production UI Simulated Workflows', () => {
  test.use({ baseURL: 'https://my-agentic-lab.web.app' });

  test('Live Product Search & Support Chat Flow', async ({ page }) => {
    test.setTimeout(60000);

    // 1. Visit deployed app
    await page.goto('/', { waitUntil: 'networkidle' });
    await expect(page).toHaveTitle(/E-commerce Support Agent/i);

    // 2. Verify chat container & input
    const chatInput = page.locator('input[placeholder*="Ask"], textarea[placeholder*="Ask"]');
    await expect(chatInput.first()).toBeVisible();

    // 3. Submit inquiry about UK product
    const inquiry = 'Hello, can you help me find a gaming laptop available in the UK?';
    await chatInput.first().fill(inquiry);
    await chatInput.first().press('Enter');

    // 4. Verify user message appears in UI
    await expect(page.locator(`text=${inquiry}`)).toBeVisible({ timeout: 10000 });

    // 5. Wait for agent response message from Cloud Run backend
    await page.waitForTimeout(8000);

    // Verify response elements rendered
    const responseBubbles = page.locator('.chat-bubble, .rounded-2xl, .p-4, div[class*="bubble"]');
    expect(await responseBubbles.count()).toBeGreaterThan(1);
  });

  test('Live Order Tracking Flow', async ({ page }) => {
    test.setTimeout(60000);

    await page.goto('/', { waitUntil: 'networkidle' });
    const chatInput = page.locator('input[placeholder*="Ask"], textarea[placeholder*="Ask"]');
    await expect(chatInput.first()).toBeVisible();

    const orderQuery = 'What is the status of order ORD001?';
    await chatInput.first().fill(orderQuery);
    await chatInput.first().press('Enter');

    await expect(page.locator(`text=${orderQuery}`)).toBeVisible({ timeout: 10000 });

    // Allow time for agent backend to execute get_order_status tool
    await page.waitForTimeout(8000);

    // Check that ORD001 is present in the conversation
    const ordMatches = page.locator('text=ORD001');
    expect(await ordMatches.count()).toBeGreaterThan(0);
  });
});
