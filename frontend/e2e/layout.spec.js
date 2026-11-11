import { test, expect } from "@playwright/test";

/**
 * No route may push the page wider than the viewport.
 *
 * The research-assistant suggestion chips are `<button class="pill">`, and `.pill` is
 * `white-space: nowrap`; at 412 px a single chip question rendered 6 px past the right edge, so
 * `documentElement.scrollWidth` was 418 and the page could be dragged sideways with the finger.
 * Nothing failed: the text was simply cut off, and the offender was one element among hundreds.
 */

const ROUTES = [
  "dashboard",
  "laboratory",
  "predictions",
  "workflow",
  "workflows",
  "assistant",
  "greenhouse",
  "comparison",
  "crops",
  "datasets",
  "analytics",
  "advisor",
  "benchmarks",
  "models",
  "account",
  "methodology",
];

test("no route overflows the viewport horizontally", async ({ page }) => {
  const offenders = [];
  for (const route of ROUTES) {
    await page.goto(`/#${route}`, { waitUntil: "networkidle" });
    const overflow = await page.evaluate(() => {
      const root = document.documentElement;
      const width = root.clientWidth;
      const excess = root.scrollWidth - width;
      const culprits = [];
      for (const el of document.querySelectorAll("body *")) {
        const box = el.getBoundingClientRect();
        if (box.width > 0 && box.right > width + 0.5)
          culprits.push(`${el.tagName}.${el.className} right=${Math.round(box.right)}`);
        if (culprits.length >= 3) break;
      }
      return { width, excess, culprits };
    });
    if (overflow.excess > 1)
      offenders.push(`${route}: ${overflow.excess}px wider than ${overflow.width}px (${overflow.culprits.join("; ")})`);
  }
  expect(offenders, "a page wider than the viewport can be dragged sideways on a phone").toEqual([]);
});

