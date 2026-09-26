import { expect, test } from '@playwright/test';
import { emailRows, watch } from './helpers';

test('primary journey: register → connect Gmail → sync & analyze → inbox → detail → dashboard → revoke/reconnect → disconnect → logout', async ({ page }) => {
  const w = watch(page);
  const email = `e2e${Date.now()}@example.com`;

  // Register (lands on the dashboard)
  await page.goto('/inbox');
  await expect(page).toHaveURL(/\/login/);
  await page.getByRole('link', { name: 'Create an account' }).click();
  await page.getByLabel('Name').fill('E2E Person');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill('Correct-Horse-9');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL('/');
  await expect(page.getByText('Connect Gmail to get started')).toBeVisible();

  // Connect Gmail through the (fake) OAuth consent — no password field anywhere
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Integrations' }).click();
  // Route chunks load lazily and the router keeps the previous page visible meanwhile.
  await expect(page.getByRole('heading', { name: 'Integrations' })).toBeVisible();
  await page.getByRole('main').getByRole('link', { name: 'Connect Gmail' }).click();
  await expect(page.locator('#allow')).toBeVisible();
  expect(await page.locator('input[type=password]').count()).toBe(0);
  await page.locator('#allow').click();
  await expect(page).toHaveURL(/\/integrations/);
  await expect(page.getByText('Gmail connected.')).toBeVisible();
  const status = page.getByTestId('current-sync-status');
  await expect(status).toContainText('Completed', { timeout: 60_000 });
  await expect(status).toContainText('Initial');

  // Inbox: emails with AI indicators appear without reload
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Inbox' }).click();
  await expect(page.getByRole('heading', { name: 'Inbox' })).toBeVisible();
  await expect(emailRows(page).first()).toBeVisible();
  await expect(page.locator('ul[aria-label=Emails]').getByText('Analyzing')).toHaveCount(0, { timeout: 90_000 });
  await expect(page.locator('ul[aria-label=Emails]').getByText('Critical').first()).toBeVisible();
  await expect(page.getByText(/1–20 of \d+/)).toBeVisible();

  // "Analyze with …" button queues the whole inbox in the backend analysis queue
  await page.getByRole('button', { name: /Analyze with/ }).click();
  await page.getByLabel('Also re-analyze emails that already have results').check();
  await page.getByRole('button', { name: 'Queue analysis' }).click();
  await expect(page.getByText(/Analysis queued for all emails/)).toBeVisible();
  await expect(page.locator('ul[aria-label=Emails]').getByText(/Analyzing|Re-analyzing/)).toHaveCount(0, { timeout: 90_000 });

  // Search + filters (reflected in URL)
  await page.getByLabel('Search emails').fill('lasagna');
  await expect(page).toHaveURL(/q=lasagna/);
  await expect(emailRows(page)).toHaveCount(1);
  await page.getByLabel('Search emails').fill('');
  await page.getByRole('button', { name: /Filters/ }).click();
  await page.locator('#inbox-filters').getByRole('button', { name: 'Critical' }).click();
  await page.getByRole('button', { name: 'Apply filters' }).click();
  await expect(page).toHaveURL(/priority=CRITICAL/);
  await expect(emailRows(page)).toHaveCount(3);
  await page.reload();
  await expect(emailRows(page)).toHaveCount(3);

  // Detail + re-analyze
  await emailRows(page).first().click();
  await expect(page.getByRole('heading', { name: 'AI analysis' })).toBeVisible();
  await expect(page.getByRole('meter', { name: 'Reply urgency' })).toBeVisible();
  await page.getByRole('button', { name: 'Re-analyze' }).click();
  await expect(page.getByRole('button', { name: 'Re-analyze' })).toBeEnabled({ timeout: 30_000 });
  await expect(page.getByText(/Model fake-classifier-1 · prompt/)).toBeVisible();

  // Dashboard + Needs Attention
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Dashboard' }).click();
  await expect(page.getByRole('heading', { name: 'Needs attention' })).toBeVisible();
  await expect(page.getByText('AI-based suggestion').first()).toBeVisible();
  await expect(page.getByRole('link', { name: /Critical \/ high/ })).toContainText(/\d+/);

  // Simulate revoked authorization → reconnect prompt → reconnect
  await page.goto('/integrations');
  await page.getByRole('button', { name: 'Simulate revoked authorization' }).click();
  await page.getByRole('button', { name: 'Sync now' }).click();
  await expect(page.getByText('Reconnect required')).toBeVisible({ timeout: 30_000 });
  await page.getByRole('main').getByRole('link', { name: 'Reconnect Gmail' }).click();
  await page.locator('#allow').click();
  await expect(page.getByText('Reconnect required')).toHaveCount(0);
  await expect(page.getByTestId('current-sync-status')).toContainText('Completed', { timeout: 60_000 });

  // Disconnect
  await page.getByRole('button', { name: 'Disconnect' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Disconnect' }).click();
  await expect(page.getByText('Connect your Gmail inbox')).toBeVisible();

  // Logout
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto('/');
  await expect(page).toHaveURL(/\/login/);

  // see security.spec.ts: the test runner's own helper script is blocked in sandboxed frames
  expect(w.errors.filter((e) => !e.includes('about:srcdoc'))).toEqual([]);
  expect(w.external).toEqual([]);
});
