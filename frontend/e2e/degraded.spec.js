import { test, expect } from "@playwright/test";

/**
 * What a page does when one of its requests fails.
 *
 * Every module used to render a secondary panel as `{data && <Panel/>}`. A failed request therefore
 * removed the panel and left nothing behind: no error, no skeleton, no hint that something was
 * missing. On the benchmarks page that is the difference between "the closed-loop and external
 * validation panels are absent" and "the API refused to answer" - and on this product an external
 * check that failed is supposed to stay visible wherever a user meets the model.
 *
 * These tests cut one endpoint out of the network and assert the page says so instead of quietly
 * shrinking. They must not depend on the backend being healthy or unhealthy for the rest of the
 * graph: only the named route is intercepted, everything else passes through to the real API.
 */

const ERROR_BANNER = ".error-banner";

async function ready(page, hash) {
  await page.goto(`/#${hash}`);
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator(".simulation-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
}

test("a failed secondary request is reported, not silently dropped", async ({
  page,
}) => {
  let aborted = 0;
  await page.route("**/api/external-validation", (route) => {
    aborted += 1;
    return route.abort();
  });

  await ready(page, "benchmarks");
  // The main benchmark payload still renders: one bad endpoint must not take the page down.
  await expect(page.getByText("Closed-chamber gas and water exchange")).toBeVisible();
  const banner = page.locator(ERROR_BANNER).first();
  await expect(banner).toBeVisible();
  await expect(banner).toHaveAttribute("role", "alert");
  expect(aborted).toBeGreaterThan(0);
});

test("the model table keeps the external-check verdict visible", async ({
  page,
}) => {
  // With the endpoint reachable, the lettuce row carries the failed external check. With it cut,
  // the row must not quietly read as if no check had ever been run: the page has to say that the
  // verdict could not be loaded.
  await ready(page, "models");
  await expect(page.getByText("Served models")).toBeVisible();
  await expect(page.getByText(/External check failed/i)).toBeVisible();

  await page.route("**/api/external-validation", (route) => route.abort());
  await page.goto("/#benchmarks");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator(ERROR_BANNER).first()).toBeVisible();
});
