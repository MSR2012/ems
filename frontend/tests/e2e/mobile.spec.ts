import { expect, test } from '@playwright/test';
import { emailRows, login, watch } from './helpers';

test('mobile: navigate via menu, browse inbox, open an email', async ({ page }) => {
  const w = watch(page);
  await login(page);
  await expect(page.getByRole('heading', { name: 'Needs attention' })).toBeVisible();
  await page.getByRole('button', { name: 'Open menu' }).click();
  await page.getByRole('dialog', { name: 'Menu' }).getByRole('link', { name: 'Inbox' }).click();
  await expect(emailRows(page).first()).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
  await emailRows(page).first().click();
  await expect(page.getByRole('heading', { name: 'AI analysis' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  expect(w.errors).toEqual([]);
});
