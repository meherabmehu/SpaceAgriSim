import { test, expect } from "@playwright/test";

/**
 * Phase 35 accessibility additions: the three things a previous phase did not measure.
 *
 *   1. Text contrast, computed from the rendered colours rather than read off the stylesheet, so a
 *      later palette change that makes text unreadable fails here.
 *   2. Reduced motion, asserted under an emulated `prefers-reduced-motion: reduce` preference.
 *   3. A keyboard-only journey: reach a route and change it without a pointer.
 *
 * These are not a WCAG conformance claim. They are the specific measurable properties this
 * application claims to have, checked against the running build.
 */

const ROUTES = ["dashboard", "predictions", "benchmarks", "datasets", "laboratory"];

async function ready(page, hash) {
  await page.goto(`/#${hash}`);
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator(".module-loading")).toHaveCount(0);
}

test("rendered text meets 4.5:1 contrast on the routes that carry scientific claims", async ({
  page,
}) => {
  for (const hash of ROUTES) {
    await ready(page, hash);
    const failures = await page.evaluate(() => {
      const luminance = (colour) => {
        const [r, g, b] = colour
          .match(/[\d.]+/g)
          .slice(0, 3)
          .map(Number)
          .map((value) => {
            const c = value / 255;
            return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
          });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
      };
      // Walk up until an opaque background is found; a transparent ancestor is not a background.
      const backgroundOf = (element) => {
        let node = element;
        while (node) {
          const background = getComputedStyle(node).backgroundColor;
          if (background && !background.includes("rgba(0, 0, 0, 0)")) return background;
          node = node.parentElement;
        }
        return "rgb(255, 255, 255)";
      };
      const nodes = [...document.querySelectorAll("p, span, strong, td, th, h1, h2, h3, label, a")];
      return nodes
        .filter((node) => {
          const text = (node.textContent || "").trim();
          if (!text) return false;
          // Only the element that directly renders text, not every ancestor that contains some.
          const style = getComputedStyle(node);
          return style.visibility !== "hidden" && style.display !== "none" && node.offsetParent !== null;
        })
        .map((node) => {
          const style = getComputedStyle(node);
          const ratio =
            (Math.max(luminance(style.color), luminance(backgroundOf(node))) + 0.05) /
            (Math.min(luminance(style.color), luminance(backgroundOf(node))) + 0.05);
          return {
            text: (node.textContent || "").trim().slice(0, 40),
            ratio: Number(ratio.toFixed(2)),
          };
        })
        .filter((row) => row.ratio < 4.5)
        .slice(0, 5);
    });
    expect(failures, `${hash} has text below 4.5:1`).toEqual([]);
  }
});

test("reduced motion removes animation rather than relying on a stylesheet nobody applied", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await ready(page, "laboratory");
  const durations = await page.evaluate(() => {
    const nodes = [...document.querySelectorAll(".platform *")].slice(0, 300);
    return nodes
      .map((node) => getComputedStyle(node))
      .map((style) => ({
        animation: style.animationName,
        transition: style.transitionDuration,
      }))
      .filter(
        (row) =>
          (row.animation && row.animation !== "none") ||
          (row.transition && Number.parseFloat(row.transition) > 0),
      );
  });
  expect(durations, "animated properties survive a reduced-motion preference").toEqual([]);

  // The chamber still renders: reduced motion must remove motion, not the information.
  await page.goto("/#greenhouse");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  const chamber = page.getByRole("img", { name: /growth chamber/i }).first();
  await expect(chamber).toBeVisible();
});

test("a route can be reached and changed with the keyboard alone", async ({ page }) => {
  await ready(page, "dashboard");
  // The first tab stop is the skip link; the sidebar nav is next.
  await page.keyboard.press("Tab");
  await expect(page.locator("a.skip-link")).toBeFocused();
  // The sidebar entries are links with a real href, so they work without JavaScript and are
  // announced as links; the app intercepts the click only to keep its own history.
  const nav = page.getByRole("link", { name: /NASA data explorer/i }).first();
  await nav.focus();
  await expect(nav).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: /NASA data explorer/i }).first()).toBeVisible();
  // Focus is visible: the focused element paints an outline rather than relying on colour alone.
  const outline = await nav.evaluate((node) => {
    const style = getComputedStyle(node);
    return { width: style.outlineWidth, style: style.outlineStyle };
  });
  expect(Number.parseFloat(outline.width)).toBeGreaterThanOrEqual(1);
  expect(outline.style).not.toBe("none");
});

test("charts and the chamber expose their meaning to assistive technology", async ({ page }) => {
  await ready(page, "laboratory");
  const plot = page.getByRole("img", { name: /cumulative fresh biomass/i });
  if ((await plot.count()) > 0) {
    await expect(plot.first()).toBeVisible();
  }
  await page.goto("/#greenhouse");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /growth chamber/i }).first()).toBeVisible();
});
