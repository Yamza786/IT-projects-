import assert from "node:assert/strict";
import axe from "axe-core";
import { chromium } from "playwright";

const baseUrl = process.env.ADAPTIVE_BASE_URL ?? "http://127.0.0.1:8765";
const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage({ viewport: { width: 320, height: 900 } });
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  const reflow = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  assert.ok(reflow.document <= reflow.viewport, `320px document overflow: ${JSON.stringify(reflow)}`);
  assert.ok(reflow.body <= reflow.viewport, `320px body overflow: ${JSON.stringify(reflow)}`);

  await page.addScriptTag({ content: axe.source });
  const audit = await page.evaluate(async () => {
    const result = await axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
    });
    return result.violations.map(({ id, impact, help, nodes }) => ({
      id, impact, help, elements: nodes.map(({ target }) => target),
    }));
  });
  assert.deepEqual(audit, [], `axe-core reported accessibility violations: ${JSON.stringify(audit, null, 2)}`);

  await page.keyboard.press("Tab");
  assert.equal(await page.evaluate(() => document.activeElement.className), "skip");
  await page.keyboard.press("Tab");
  assert.equal(await page.evaluate(() => document.activeElement.textContent.trim()), "Practice this lesson");
  await page.keyboard.press("Enter");
  await page.locator("#quiz-title").waitFor();
  await page.waitForFunction(() => document.activeElement.id === "quiz-title");
  await page.keyboard.press("Tab");
  await page.keyboard.press("ArrowDown");
  assert.equal(await page.locator('input[type="radio"]:checked').count(), 1);
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.getElementById("feedback").textContent.startsWith("Correct."));

  await page.setViewportSize({ width: 640, height: 900 });
  const zoomedReflow = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  assert.ok(zoomedReflow.document <= zoomedReflow.viewport, `narrow reflow overflow: ${JSON.stringify(zoomedReflow)}`);
  assert.ok(zoomedReflow.body <= zoomedReflow.viewport, `narrow body overflow: ${JSON.stringify(zoomedReflow)}`);
  console.log("Chromium axe, keyboard quiz flow, focus movement, and narrow-screen reflow passed.");
} finally {
  await browser.close();
}
