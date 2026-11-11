import { test, expect } from "@playwright/test";
import { settleForCapture } from "./settle.js";

/**
 * Phase 35: capture the pages a researcher uses to judge a number, not only the dashboard.
 *
 * The gate used to cover the mission shell, the two radiation cards and the water panel. The
 * model-registry and benchmark pages are where a reader decides whether to trust a value, so their
 * layout is now compared too. One capture per route per viewport, written to the gitignored output
 * tree; the committed baseline is refreshed deliberately, never by this test.
 */
const ROUTES = [
  { hash: "predictions", name: "predictions" },
  { hash: "benchmarks", name: "benchmarks" },
];

for (const route of ROUTES) {
  test(`capture the ${route.name} route at every viewport`, async ({ page }, testInfo) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(`/#${route.hash}`);
    await expect(page.getByText("API connected", { exact: true })).toBeVisible();
    // A page that is still loading would be captured as a skeleton, so wait for content.
    await expect(page.locator(".module-loading")).toHaveCount(0);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy();
    expect(errors).toEqual([]);
    await settleForCapture(page);
    await page.screenshot({
      path: `test-results/screenshots/${route.name}-${testInfo.project.name}.png`,
      fullPage: true,
    });
  });
}

test("the model registry shows an evidence verdict on every card", async ({ page }) => {
  // The badge is what carries the Phase 35 claim to a reader, so its presence is asserted rather
  // than only photographed.
  await page.goto("/#predictions");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  const cards = page.locator(".module-grid .mission-card");
  const count = await cards.count();
  expect(count).toBeGreaterThanOrEqual(7);
  await expect(page.getByText("Independent check failed").first()).toBeVisible();
  await expect(page.getByText("No independent check").first()).toBeVisible();
  const failed = page.locator('.pill', { hasText: "Independent check failed" });
  expect(await failed.count()).toBeGreaterThanOrEqual(3);
});
