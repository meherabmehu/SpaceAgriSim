import { test, expect } from "@playwright/test";
import { settleForCapture } from "./settle.js";

/**
 * Phase 35: capture the pages a researcher uses to judge a number, not only the dashboard.
 *
 * The gate used to cover the mission shell, the two radiation cards and the water panel. The
 * model-registry and benchmark pages are where a reader decides whether to trust a value, so their
 * layout is compared too.
 *
 * Capture and assertion are separate tests on purpose: a capture must still be written when an
 * assertion fails, otherwise a regression would silently remove the evidence of itself, and the
 * parent commit - which has the bug this phase fixes - would produce no capture to compare against.
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
    // A page that is still loading would be captured as a skeleton.
    await expect(page.locator(".module-loading")).toHaveCount(0);
    // The benchmarks page fills in rows from two API calls; wait for the content itself rather
    // than for a duration, so the capture is of the same state on both trees.
    if (route.hash === "benchmarks") {
      await expect(page.locator(".bench-row").first()).toBeVisible();
    }
    expect(errors).toEqual([]);
    await settleForCapture(page);
    // Bound the capture: these two routes stack every model and benchmark row, and an unbounded
    // full-page capture crashes the renderer at that size. The top 6 000 px carry the status panel
    // and the first rows, which is what a layout regression would move.
    const height = await page.evaluate(() =>
      Math.min(document.documentElement.scrollHeight, 6000),
    );
    await page.screenshot({
      path: `test-results/screenshots/${route.name}-${testInfo.project.name}.png`,
      clip: { x: 0, y: 0, width: page.viewportSize().width, height },
    });
  });
}

for (const route of ROUTES) {
  test(`the ${route.name} route does not scroll sideways at any viewport`, async ({ page }, testInfo) => {
    await page.goto(`/#${route.hash}`);
    await expect(page.getByText("API connected", { exact: true })).toBeVisible();
    await expect(page.locator(".module-loading")).toHaveCount(0);
    if (route.hash === "benchmarks") {
      await expect(page.locator(".bench-row").first()).toBeVisible();
    }
    const overflow = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      client: document.documentElement.clientWidth,
    }));
    // Phase 35 fixed the first case this test ever caught: a benchmark row's citation forced the
    // document 83 px wider than a tablet viewport (903 against 820) because grid items default to
    // `min-width: auto`. One pixel of tolerance covers sub-pixel layout, not a moved element.
    expect(
      overflow.scroll,
      `${route.name} overflows horizontally at ${testInfo.project.name}`,
    ).toBeLessThanOrEqual(overflow.client + 1);
  });
}

test("the model registry shows an evidence verdict on every card", async ({ page }) => {
  // The badge is what carries the Phase 35 claim to a reader, so its presence is asserted rather
  // than only photographed.
  await page.goto("/#predictions");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  const cards = page.locator(".module-grid .mission-card");
  // The registry is assembled per request, so wait for the first card before counting;
  // the assertion itself is unchanged.
  await expect(cards.first()).toBeVisible();
  expect(await cards.count()).toBeGreaterThanOrEqual(7);
  await expect(page.getByText("Independent check failed").first()).toBeVisible();
  await expect(page.getByText("No independent check").first()).toBeVisible();
  const failed = page.locator(".pill", { hasText: "Independent check failed" });
  expect(await failed.count()).toBeGreaterThanOrEqual(3);
});
