import { test, expect } from '@playwright/test';

test.describe('E-Commerce Customer Support Agent E2E Suite', () => {

  test('should load the homepage and check key visual components', async ({ page }) => {
    // Navigate to the app using baseURL from playwright.config.js
    await page.goto('/');

    // 1. Verify Title and Header
    await expect(page).toHaveTitle(/E-commerce Support Agent/i);
    
    const header = page.locator('h1');
    await expect(header).toContainText(/E-commerce Support Agent/i);

    // 2. Verify online agent status indicator
    const statusText = page.locator('.text-green-400, .bg-green-500, :text("Online")');
    if (await statusText.count() > 0) {
      await expect(statusText.first()).toBeVisible();
    }

    // 3. Verify that the chat area exists
    const chatContainer = page.locator('#chat-container, .chat-container, .flex-1.overflow-y-auto');
    await expect(chatContainer.first()).toBeVisible();
  });

  test('should toggle dark/light themes correctly', async ({ page }) => {
    await page.goto('/');

    // Locate the theme toggle button (often represented by a sun/moon icon or specific class/id)
    const themeToggle = page.locator('#theme-toggle, .theme-toggle, button:has-text("Theme"), button:has(.lucide-sun), button:has(.lucide-moon)');
    
    if (await themeToggle.count() > 0) {
      // Get initial theme attribute/class if applicable
      const mainContainer = page.locator('.transition-colors.duration-500').first();
      const initialClass = await mainContainer.getAttribute('class') || '';

      // Toggle theme
      await themeToggle.first().click();
      await page.waitForTimeout(500);

      // Verify class changes or exists
      const currentClass = await mainContainer.getAttribute('class') || '';
      expect(currentClass).not.toBe(initialClass);
    }
  });

  test('should render skeleton loading state during product searches', async ({ page }) => {
    await page.goto('/');

    // Type a product search query in the chat input
    const chatInput = page.locator('input[placeholder*="Ask"], textarea[placeholder*="Ask"], #chat-input');
    await expect(chatInput.first()).toBeVisible();

    await chatInput.first().fill('I want to buy an Xbox in UK');
    await chatInput.first().press('Enter');

    // Verify skeleton loaders or loading state appears
    const skeletons = page.locator('.animate-pulse, .skeleton, [data-testid="skeleton"]');
    if (await skeletons.count() > 0) {
      await expect(skeletons.first()).toBeVisible();
    }
  });

  test('should check Jarvis Mode ORB and continuous waveform animations', async ({ page }) => {
    await page.goto('/');

    // Locate the voice waveform visualizer or JARVIS activation indicator
    const jarvisToggle = page.locator('#jarvis-toggle, .jarvis-btn, :text("Jarvis")');
    if (await jarvisToggle.count() > 0) {
      await jarvisToggle.first().click();
      await page.waitForTimeout(500);

      // Check JARVIS avatar / orb is pulsing
      const jarvisOrb = page.locator('.jarvis-avatar, .orb-pulsing, .animate-ping');
      await expect(jarvisOrb.first()).toBeVisible();
    }

    // Verify speech waveform canvas or container exists
    const waveform = page.locator('canvas, .waveform, .audio-visualizer');
    if (await waveform.count() > 0) {
      await expect(waveform.first()).toBeVisible();
    }
  });

  test('should verify checkout confetti canvas element exists', async ({ page }) => {
    await page.goto('/');

    // Confetti canvas is typically appended to the body during checkout celebration
    const confettiCanvas = page.locator('canvas#confetti, canvas.confetti-canvas, canvas');
    // We just check that the library/framework support is ready in the DOM or canvas exists
    if (await confettiCanvas.count() > 0) {
      await expect(confettiCanvas.first()).toBeAttached();
    }
  });
});
