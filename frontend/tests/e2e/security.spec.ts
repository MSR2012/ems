import { expect, test } from '@playwright/test';
import { emailRows, login, watch } from './helpers';

test('malicious HTML email renders safely: no script, no remote requests, no console errors', async ({ page }) => {
  const w = watch(page);
  await login(page);
  await page.goto('/inbox?q=weekly+summary');
  await emailRows(page).filter({ hasText: 'HTML test' }).click();
  await expect(page.locator('iframe[title="Email content"]')).toBeVisible();
  await page.waitForTimeout(2000);
  // The Playwright *test runner* injects its helper script into every frame; the sandbox
  // (correctly) blocks it and Chrome logs "Blocked script execution in 'about:srcdoc'".
  // The app itself puts no script in the frame — asserted directly on the srcdoc below.
  const srcdoc = (await page.locator('iframe[title="Email content"]').getAttribute('srcdoc')) ?? '';
  expect(srcdoc).not.toMatch(/<script|onerror|onclick|onload|javascript:|tracker\.example\.com/i);
  expect(srcdoc).toContain("default-src 'none'");
  expect(w.errors.filter((e) => !e.includes('about:srcdoc'))).toEqual([]);
  expect(w.dialogs).toEqual([]);
  expect(w.external).toEqual([]);
  const frame = page.frameLocator('iframe[title="Email content"]');
  await expect(frame.getByText('Your weekly account summary')).toBeVisible();
  expect(await page.locator('iframe[title="Email content"]').getAttribute('sandbox')).not.toContain('allow-scripts');
  await expect(frame.locator('script')).toHaveCount(0);
  expect(w.dialogs).toEqual([]);
  expect(w.external).toEqual([]);
  expect(w.errors.filter((e) => !e.includes("about:srcdoc"))).toEqual([]);
});

test('another user cannot open the demo user\'s email', async ({ page, request }) => {
  await login(page);
  await page.goto('/inbox');
  await emailRows(page).first().click();
  const url = page.url();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await login(page, 'other@example.com', 'OtherPass123!');
  await page.goto(url);
  await expect(page.getByText('Email not found')).toBeVisible();
  const anon = await request.get(url.replace('/emails/', '/api/v1/emails/'));
  expect(anon.status()).toBe(401);
});
