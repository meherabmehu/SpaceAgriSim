import { test, expect } from "@playwright/test";

/**
 * Every route, on every viewport, loads without a single complaint.
 *
 * The bug audit found two defects that a page-by-page assertion would have missed but this sweep
 * catches by construction: a request to `GET /apinull` that 404'd in every signed-out console, and
 * a red "Authentication is required" banner rendered from a 401 on a page that had no session to
 * begin with. Both rendered, both were silent, and both were only visible in the console and the
 * network log — which is exactly what this test reads.
 *
 * A failure here names the route, so the report says where to look rather than only that something
 * happened somewhere.
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

test("no route produces a console error, a failed request or horizontal overflow", async ({
  page,
}) => {
  const problems = [];
  let route = "(start)";

  page.on("pageerror", (error) => problems.push(`${route}: page error - ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`${route}: console - ${message.text()}`);
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      problems.push(`${route}: ${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });

  for (const name of ROUTES) {
    route = name;
    await page.goto(`/#${name}`, { waitUntil: "networkidle" });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    if (overflow > 0) problems.push(`${name}: ${overflow}px wider than the viewport`);
  }

  expect(problems).toEqual([]);
});
