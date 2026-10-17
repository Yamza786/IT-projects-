import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const baseUrl = process.env.PORTFOLIO_BASE_URL ?? 'http://127.0.0.1:8766/portfolio-command-center/';
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(baseUrl, { waitUntil: 'networkidle' });
  await page.getByRole('heading', { name: 'IT/CS Portfolio', exact: true }).waitFor();
  await page.locator('.card').first().waitFor();
  assert.equal(await page.locator('.card').count(), 25, 'renders all portfolio entries');
  assert.match(await page.locator('#count').innerText(), /Showing 25 of 25 projects/);

  const search = page.getByRole('searchbox', { name: 'Search projects' });
  await search.fill('security');
  assert.equal(await page.locator('.card').count(), 4, 'search filters project names, categories, and summaries');

  await search.fill('');
  await page.getByRole('button', { name: 'Security', exact: true }).click();
  assert.equal(await page.locator('.card').count(), 4, 'category filter selects matching projects');

  await page.setViewportSize({ width: 320, height: 700 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  assert.equal(overflow, false, 'layout reflows without horizontal overflow at 320px');
  console.log('Portfolio command center browser checks passed.');
} finally {
  await browser.close();
}
