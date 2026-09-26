import { expect, type Page } from '@playwright/test';

/** Collects console errors / page errors and requests leaving the app origin. */
export function watch(page: Page) {
  const errors: string[] = [];
  const external: string[] = [];
  const dialogs: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('dialog', (d) => { dialogs.push(d.message()); void d.dismiss(); });
  page.on('request', (r) => {
    const u = r.url();
    if (!u.startsWith('http://localhost:5173') && !u.startsWith('data:') && !u.startsWith('about:')) external.push(u);
  });
  return { errors, external, dialogs };
}

export async function login(page: Page, email = 'demo@example.com', password = 'DemoPass123!') {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL('/');
}

export const emailRows = (page: Page) => page.locator('ul[aria-label=Emails] > li');
