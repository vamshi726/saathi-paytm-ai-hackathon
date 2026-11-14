import { expect, test } from '@playwright/test';
test('connected UI investigates and verifies the actual persisted backend case', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByLabel('Local demo bearer token').fill('ui-smoke-only-token');
  await page.getByRole('button', { name: 'Connect to local backend' }).click();
  await expect(page.getByRole('heading', { name: 'CS-1043', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Run investigation' }).click();
  await expect(page.getByText('Your payment is confirmed and your mock order is now PAID.', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Independent order read-back completed.')).toBeVisible();
  await page.getByRole('button', { name: 'Refresh', exact: false }).click();
  await expect(page.getByRole('button', { name: 'Run investigation' })).toBeDisabled();
  await page.screenshot({ path: '../.runtime/saathi-connected.png', fullPage: true });
  await page.reload();
  await expect(page.getByLabel('Local demo bearer token')).toHaveValue('');
  expect(errors).toEqual([]);
});
test('mobile rehearsal supports same-case clarification and preserves state on reload', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Open UI rehearsal' }).click();
  await page.getByRole('button', { name: /CS-1046/ }).click();
  await page.getByRole('button', { name: 'Run investigation' }).click();
  await page.getByLabel('Customer reply').fill('ORD-2046');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(page.getByText(/Only one completed charge is confirmed/).first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '../.runtime/saathi-mobile.png', fullPage: true });
  await page.reload();
  await page.getByRole('button', { name: 'Open UI rehearsal' }).click();
  await page.getByRole('button', { name: /CS-1046/ }).click();
  await expect(page.getByText(/Only one completed charge is confirmed/).first()).toBeVisible();
});

