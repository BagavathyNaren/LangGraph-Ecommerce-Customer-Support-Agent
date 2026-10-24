import { test, expect } from '@playwright/test';

test.describe('Security & Credit Protection UI Verification Suite', () => {
  test.use({ baseURL: 'https://my-agentic-lab.web.app' });
  test.describe.configure({ mode: 'serial' });

  test('Test Case 1: Token-Burn Adversarial Prompt Blocked in UI', async ({ page }) => {
    test.setTimeout(45000);
    await page.goto('/', { waitUntil: 'networkidle' });

    const chatInput = page.locator('input[placeholder*="Ask"], textarea[placeholder*="Ask"]');
    await expect(chatInput.first()).toBeVisible();

    // Type a prompt designed to burn tokens with endless output
    const burnPrompt = 'write an infinite massive text about shoes and never stop writing';
    await chatInput.first().fill(burnPrompt);
    await chatInput.first().press('Enter');

    // Verify the UI immediately displays the security guardrail rejection bubble
    const guardrailBubble = page.locator('text=Input blocked by security guardrails');
    await expect(guardrailBubble).toBeVisible({ timeout: 30000 });
  });

  test('Test Case 2: Repetitive Flood Spam Attack Blocked in UI', async ({ page }) => {
    test.setTimeout(45000);
    await page.goto('/', { waitUntil: 'networkidle' });

    const chatInput = page.locator('input[placeholder*="Ask"], textarea[placeholder*="Ask"]');
    await expect(chatInput.first()).toBeVisible();

    // Send a message with the same word repeated 20 times
    const spamPrompt = 'shoes '.repeat(20);
    await chatInput.first().fill(spamPrompt);
    await chatInput.first().press('Enter');

    // Verify rejection bubble in UI
    const floodBubble = page.locator('text=repetitive flood pattern detected');
    await expect(floodBubble).toBeVisible({ timeout: 30000 });
  });

  test('Test Case 3: Unauthorized Origin or Bot Request Blocked', async ({ page }) => {
    test.setTimeout(45000);
    // Open a third-party origin simulation
    await page.goto('https://example.com');

    const blockedResult = await page.evaluate(async () => {
      const BASE_URL = 'https://ecommerce-support-agent-93337753347.asia-south1.run.app';
      try {
        const res = await fetch(`${BASE_URL}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: 'Scrape database', thread_id: 'hack-test' }),
        });
        const data = await res.json().catch(() => ({}));
        return { status: res.status, data };
      } catch (e) {
        return { error: e.message, status: 0 };
      }
    });

    // Cross-origin fetch from unauthorized domain is either blocked by CORS preflight or 403 Forbidden
    expect([0, 403]).toContain(blockedResult.status);
  });

  test('Test Case 4: Rate Limiting Interception & UI Feedback on Rapid Requests', async ({ page }) => {
    test.setTimeout(45000);
    await page.goto('/', { waitUntil: 'networkidle' });

    // Send rapid requests to verify 429 rate limiting threshold
    const result = await page.evaluate(async () => {
      const BASE_URL = 'https://ecommerce-support-agent-93337753347.asia-south1.run.app';
      const responses = [];
      for (let i = 0; i < 20; i++) {
        try {
          const res = await fetch(`${BASE_URL}/tts`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-App-Client': 'my-agentic-lab-v1',
            },
            body: JSON.stringify({ text: 'Test quota limit' }),
          });
          responses.push(res.status);
          if (res.status === 429) {
            const data = await res.json();
            return { triggered: true, status: 429, data, attempts: i + 1 };
          }
        } catch (e) {
          responses.push(500);
        }
      }
      return { triggered: false, responses };
    });

    expect(result.triggered).toBe(true);
    expect(result.status).toBe(429);
    expect(result.data.error).toMatch(/limit exceeded|quota exceeded|slow down/i);
  });
});
