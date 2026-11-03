import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const baseUrl = process.env.PORTFOLIO_BASE_URL ?? 'http://127.0.0.1:8766/portfolio-command-center/';
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(baseUrl, { waitUntil: 'networkidle' });
  await page.getByRole('heading', { name: 'IT/CS Portfolio', exact: true }).waitFor();
  await page.locator('.card').first().waitFor();
  assert.equal(await page.locator('.card').count(), 60, 'renders every project in all three catalog collections');
  assert.match(await page.locator('#count').innerText(), /Showing 60 of 60 projects/);

  const search = page.getByRole('searchbox', { name: 'Search projects' });
  await search.fill('security');
  assert.equal(await page.locator('.card').count(), 10, 'search filters across the full catalog');

  await search.fill('Julia');
  assert.equal(await page.locator('.card').count(), 1, 'search includes project technology stacks');
  assert.equal(await page.locator('.card h2').innerText(), 'Fraud and Anomaly Detection Workbench');

  await search.fill('');
  await page.getByRole('button', { name: 'Security', exact: true }).click();
  assert.equal(await page.locator('.card').count(), 10, 'category filter selects matching projects');

  await page.setViewportSize({ width: 320, height: 700 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  assert.equal(overflow, false, 'layout reflows without horizontal overflow at 320px');
  console.log('Portfolio command center browser checks passed.');
} finally {
  await browser.close();
}
