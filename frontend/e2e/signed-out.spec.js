import { test, expect } from "@playwright/test";

/**
 * A page may not request a resource it has not got a URL for, and may not ask for what it cannot
 * have.
 *
 * `useResource(path)` was called with `null` for an authenticated resource the visitor had no
 * session for, and `fetch(`${base}${path}`)` turned that into `GET /apinull` - a 404 in every
 * console, on the account page, signed out. The same class of mistake put a red "Authentication is
 * required" banner on the analytics page next to the text explaining that the list needs a sign-in.
 *
 * Both are silent: the page renders, the console fills with 404/401s, and a user reads the banner
 * as a broken product rather than as a sign-in prompt.
 */

async function signedOut(page) {
  // The suite runs against a real API; a session left behind by another spec would make the
  // signed-out assertions meaningless.
  await page.addInitScript(() => localStorage.removeItem("spaceagrisim.auth"));
}

test("the signed-out account page does not request a placeholder path", async ({ page }) => {
  const missing = [];
  const bad = [];
  page.on("response", (response) => {
    if (response.status() === 404) missing.push(response.url());
    if (response.status() >= 400) bad.push(`${response.status()} ${response.url()}`);
  });
  await signedOut(page);
  await page.goto("/#account", { waitUntil: "networkidle" });
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();

  expect(missing, "a 404 means a request was made to a URL that does not exist").toEqual([]);
  expect(
    bad,
    "signed out, the account page must not ask the API for anything it will refuse",
  ).toEqual([]);
  // The specific shape of the old bug, asserted directly so it cannot come back by another route.
  expect(await page.evaluate(() => performance.getEntriesByType("resource").map((e) => e.name))).not.toContainEqual(
    expect.stringMatching(/\/api(null|undefined)$/),
  );
});

test("the signed-out analytics page does not ask for private history", async ({ page }) => {
  let scenarioRequests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/scenarios")) scenarioRequests += 1;
  });
  await signedOut(page);
  await page.goto("/#analytics", { waitUntil: "networkidle" });
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Saved scenarios", exact: true })).toBeVisible();

  // The card explains that the list is private, and offers nothing that looks like a failure.
  await expect(page.getByText(/Sign in to view scenarios saved to your account/)).toBeVisible();
  await expect(page.locator(".error-banner")).toHaveCount(0);
  expect(scenarioRequests, "GET /api/scenarios is authenticated; signed out it can only 401").toBe(0);
});

test("signed in, the same card lists the account's saved scenarios", async ({ page }) => {
  // The signed-out gate must not be a permanent gate: with a session the list still has to load,
  // and the restore action has to be there for each row.
  const email = `analytics-${test.info().project.name}-${Date.now()}@example.test`;
  const registered = await page.request.post("/api/auth/register", {
    data: { email, password: "CorrectHorseBattery1!" },
  });
  expect(registered.status()).toBe(201);
  const session = await registered.json();
  const created = await page.request.post("/api/scenarios", {
    headers: { Authorization: `Bearer ${session.accessToken}` },
    data: {
      name: "Analytics visibility check",
      configuration: {
        crop: "lettuce",
        radiation: 0.3,
        waterAvailability: 90,
        lightHours: 16,
        co2Level: 800,
        growingArea: 30,
        simulationDays: 30,
        earthComparisonMode: "matched",
        lightIntensity: 300,
        temperature: 22,
        humidity: 65,
        lightSpectrum: "red-blue",
        waterRecyclingEfficiency: 90,
      },
    },
  });
  expect(created.status()).toBe(201);
  await page.addInitScript((value) => localStorage.setItem("spaceagrisim.auth", JSON.stringify(value)), session);

  await page.goto("/#analytics", { waitUntil: "networkidle" });
  await expect(page.getByText("Analytics visibility check")).toBeVisible();
  await expect(page.getByRole("button", { name: "Restore", exact: true }).first()).toBeVisible();
  await expect(page.locator(".error-banner")).toHaveCount(0);
});
