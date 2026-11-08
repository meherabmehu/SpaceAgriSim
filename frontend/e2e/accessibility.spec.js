import { test, expect } from "@playwright/test";

/**
 * Accessibility checks that do not need a rule engine: the things a person navigating with a
 * keyboard or a screen reader would hit immediately.
 *
 * These are structural assertions, not a conformance claim. No axe-core run is included on
 * purpose - adding a dependency to the test suite to assert what can be asserted directly is not
 * worth the supply-chain surface - so this file is explicitly narrower than WCAG and says so.
 */

const PAGES = [
  ["dashboard", "Mission control"],
  ["laboratory", "Simulation lab"],
  ["predictions", "AI prediction center"],
  ["workflow", "Scientific workflow"],
  ["assistant", "Research assistant"],
  ["comparison", "World comparison"],
  ["crops", "Crop intelligence"],
  ["datasets", "NASA data explorer"],
  ["analytics", "Mission analytics"],
  ["advisor", "Mission advisor"],
  ["methodology", "Methodology"],
];

test("every workspace page has one h1, a skip link and reachable navigation", async ({ page }) => {
  for (const [hash] of PAGES) {
    await page.goto(`/#${hash}`);
    await expect(page.getByText("API connected", { exact: true })).toBeVisible();

    // Exactly one h1: more than one makes the document outline meaningless.
    await expect(page.locator("h1")).toHaveCount(1);

    // The skip link is the first focusable element and points at real content.
    const skip = page.locator("a.skip-link");
    await expect(skip).toHaveAttribute("href", "#mission-content");
    await expect(page.locator("#mission-content")).toHaveCount(1);

    // Heading levels never skip downward by more than one.
    const levels = await page
      .locator("h1, h2, h3, h4")
      .evaluateAll((nodes) => nodes.map((node) => Number(node.tagName.slice(1))));
    for (let index = 1; index < levels.length; index += 1) {
      expect(levels[index] - levels[index - 1]).toBeLessThanOrEqual(1);
    }
  }
});

test("interactive controls have accessible names", async ({ page }) => {
  for (const [hash] of PAGES) {
    await page.goto(`/#${hash}`);
    await expect(page.getByText("API connected", { exact: true })).toBeVisible();
    const unnamed = await page
      .locator("button, a[href], input, select, textarea")
      .evaluateAll((nodes) =>
        nodes
          .filter((node) => {
            const hidden = node.closest("[aria-hidden='true']");
            if (hidden) return false;
            const label =
              node.getAttribute("aria-label") ||
              node.getAttribute("title") ||
              node.textContent?.trim() ||
              node.getAttribute("placeholder") ||
              "";
            const labelled = node.id && document.querySelector(`label[for="${node.id}"]`);
            const wrapped = node.closest("label");
            return !label && !labelled && !wrapped;
          })
          .map((node) => `${node.tagName}:${node.className}`),
      );
    expect(unnamed, `${hash} has unnamed controls`).toEqual([]);
  }
});

test("the skip link is the first focus stop and focus is visible", async ({ page }) => {
  await page.goto("/#dashboard");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await page.keyboard.press("Tab");
  const focused = await page.evaluate(() => ({
    className: document.activeElement?.className || "",
    text: document.activeElement?.textContent?.trim() || "",
  }));
  expect(focused.className).toContain("skip-link");
  expect(focused.text.length).toBeGreaterThan(0);
});

test("dynamic regions announce their state rather than changing silently", async ({ page }) => {
  await page.goto("/#workflow");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator(".simulation-content")).toHaveAttribute("aria-busy", "false");

  await page.goto("/#assistant");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  const search = page.getByRole("searchbox", {
    name: "Ask a question about the repository evidence",
  });
  await expect(search).toBeVisible();
  // Asking with an empty box must produce an announced error, not a silent no-op.
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
});

test("the workflow page remains usable at every viewport the suite runs", async ({ page }, testInfo) => {
  await page.goto("/#workflow");
  await page.reload();
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();

  // No horizontal overflow: a page that scrolls sideways on a phone is unusable even if every
  // control is technically present.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, `horizontal overflow on ${testInfo.project.name}`).toBeLessThanOrEqual(2);

  // Every input of the selected model is reachable by label.
  await page.getByRole("button", { name: /Lettuce Earth growth/ }).first().click();
  for (const feature of ["daysAfterTransplant", "airTemperature", "rootTemperature", "ppfd"]) {
    const field = page.getByLabel(`${feature} value`);
    await field.scrollIntoViewIfNeeded();
    await expect(field).toBeVisible();
  }
});
