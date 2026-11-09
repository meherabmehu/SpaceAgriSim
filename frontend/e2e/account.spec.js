import { test, expect } from "@playwright/test";

/**
 * Phase 19: account lifecycle, sharing and the two new transparency pages.
 *
 * These tests assert the properties that would make the feature dishonest if they broke:
 *
 *  · a password reset retires the session it was requested from;
 *  · a share link opens without an account and never shows whose scenario it is;
 *  · a revoked share link stops answering;
 *  · the benchmark page shows the measured number next to the modelled one, gaps included;
 *  · the model comparison page shows each model's own baseline and does not rank them.
 */

const PASSWORD = "CorrectHorseBattery1!";
const NEW_PASSWORD = "AnotherGoodPassphrase9!";

async function ready(page, hash = "dashboard") {
  await page.goto(`/#${hash}`);
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator(".simulation-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
}

async function apiSignIn(page, email, password) {
  // The session lives in localStorage, so a token from the API is enough to exercise the
  // signed-in UI without driving the dialog for every test.
  const response = await page.request.post("/api/auth/login", {
    data: { email, password },
  });
  expect(response.ok()).toBeTruthy();
  const session = await response.json();
  await page.addInitScript((value) => {
    localStorage.setItem("spaceagrisim.auth", JSON.stringify(value));
  }, session);
  return session;
}

async function readSession(page) {
  const session = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("spaceagrisim.auth") || "null"),
  );
  expect(session?.accessToken).toBeTruthy();
  return session;
}

async function registerViaApi(page, email) {
  const response = await page.request.post("/api/auth/register", {
    data: { email, password: PASSWORD },
  });
  expect(response.status()).toBe(201);
  return response.json();
}

test("an account can save a scenario and share it without exposing the owner", async ({
  page,
  browser,
}, testInfo) => {
  const email = `share-${testInfo.project.name}-${Date.now()}@example.test`;
  await registerViaApi(page, email);

  // A saved scenario needs a signed-in browser, so the session is injected directly.
  await apiSignIn(page, email, PASSWORD);
  await ready(page, "laboratory");
  const token = (await readSession(page)).accessToken;
  const saved = await page.request.post("/api/scenarios", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `Shared ${testInfo.project.name}`,
      configuration: {
        crop: "lettuce",
        gravity: 1,
        radiation: 0.01,
        lightHours: 12,
        co2Level: 420,
        humidity: 60,
        waterAvailability: 100,
        simulationDays: 30,
      },
    },
  });
  expect(saved.status()).toBe(201);

  await ready(page, "account");
  await expect(
    page.getByRole("heading", { name: /what this deployment actually guarantees/i }),
  ).toBeVisible();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await expect(page.getByText("not verified", { exact: true })).toBeVisible();

  const row = page.locator(".scenario-list > li").first();
  await expect(row).toContainText(`Shared ${testInfo.project.name}`);
  await row.getByRole("button", { name: "Share" }).click();
  const url = await row.locator(".share-url code").innerText();
  expect(url).toContain("#shared/");

  // Open the shared page in a clean context: no session, no account data.
  const reader = await browser.newContext();
  const sharedPage = await reader.newPage();
  await sharedPage.goto(url.replace(/^https?:\/\/[^/]+/, ""));
  await expect(
    sharedPage.getByRole("heading", { name: `Shared ${testInfo.project.name}` }),
  ).toBeVisible();
  await expect(
    sharedPage.getByText(/Read-only shared scenario/).first(),
  ).toBeVisible();
  const body = await sharedPage.locator("body").innerText();
  expect(body).not.toContain(email);
  expect(body.toLowerCase()).not.toContain("owner");

  // Revoking from the account page must make that link stop answering.
  await row.getByRole("button", { name: "Revoke links" }).click();
  await expect(page.getByText(/link revoked|links revoked/)).toBeVisible();
  await sharedPage.reload();
  await expect(
    sharedPage.getByRole("heading", { name: /not available/i }),
  ).toBeVisible();
  await reader.close();
});

test("a password reset signs the old session out", async ({ page }, testInfo) => {
  const email = `reset-${testInfo.project.name}-${Date.now()}@example.test`;
  await registerViaApi(page, email);
  await apiSignIn(page, email, PASSWORD);

  await ready(page, "account");
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  const oldToken = (await readSession(page)).accessToken;

  // The development server has no SMTP, so the reset token is returned directly.
  const forgot = await page.request.post("/api/auth/password/forgot", {
    data: { email },
  });
  expect(forgot.status()).toBe(202);
  const { debugToken } = await forgot.json();
  expect(debugToken).toBeTruthy();

  await page.goto(`/#reset?token=${debugToken}`);
  await expect(
    page.getByRole("heading", { name: "Choose a new password" }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "New password" })
    .fill(NEW_PASSWORD);
  await page.getByRole("button", { name: "Choose a new password" }).click();
  await expect(
    page.getByText(/Every session issued before this change is now invalid/),
  ).toBeVisible();

  // The stored session is gone, and the old password no longer works.
  const stale = await page.request.get("/api/auth/me", {
    headers: { Authorization: `Bearer ${oldToken}` },
  });
  expect(stale.status()).toBe(401);
  const oldLogin = await page.request.post("/api/auth/login", {
    data: { email, password: PASSWORD },
  });
  expect(oldLogin.status()).toBe(401);
  const newLogin = await page.request.post("/api/auth/login", {
    data: { email, password: NEW_PASSWORD },
  });
  expect(newLogin.ok()).toBeTruthy();
});

test("benchmarks show the measured number beside the modelled one", async ({
  page,
}) => {
  await ready(page, "benchmarks");
  await expect(
    page.getByRole("heading", { name: /what NASA measured/i }),
  ).toBeVisible();

  // The chamber's measured CO2 fixation and the leafy anchor come from pinned artifacts.
  await expect(
    page.getByText("CO₂ fixed, net (g m⁻² d⁻¹)"),
  ).toBeVisible();
  await expect(page.getByText("59.5 g m⁻² day⁻¹")).toBeVisible();

  // The CO2 factor is evaluated by the model, so all three reference points are present.
  // The UI formats thousands, so the rendered labels are "420 ppm", "1,000 ppm" and "3,000 ppm".
  await expect(page.locator(".bench-row", { hasText: "420 ppm" })).toBeVisible();
  await expect(page.locator(".bench-row", { hasText: "1,000 ppm" })).toBeVisible();
  await expect(page.locator(".bench-row", { hasText: "3,000 ppm" })).toBeVisible();
  await expect(
    page.getByText(/still rises, but the published soybean chamber data/i),
  ).toBeVisible();
});

test("the model comparison shows each baseline and no ranking", async ({ page }) => {
  await ready(page, "models");
  await expect(
    page.getByRole("heading", { name: /Every served model/i }),
  ).toBeVisible();
  // Wait for the registry payload rather than sampling the DOM once: the table fills after the
  // fetch resolves, and an immediate count() would read zero on a slow runner.
  const rows = page.locator(".compare-table tbody tr");
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThan(0);
  await expect(page.locator(".compare-table thead")).toContainText("Baseline");
  await expect(page.getByText(/It does not rank models/i)).toBeVisible();
});
