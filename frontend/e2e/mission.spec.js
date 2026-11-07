import { test, expect } from "@playwright/test";

async function ready(page, hash = "dashboard") {
  await page.goto(`/#${hash}`);
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator(".simulation-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
}
test("mission shell, real controls, and responsive navigation", async ({
  page,
}, testInfo) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await ready(page);
  await expect(
    page.getByRole("heading", { name: "Mission control." }),
  ).toBeVisible();
  await expect(page.locator(".metric-tile")).toHaveCount(4);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: `../docs/screenshots/mission-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("button", { name: "Open simulation lab" }).click();
  await expect(
    page.getByRole("heading", { name: "Habitat parameters" }),
  ).toBeVisible();
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/simulate") &&
      r.request().postDataJSON().lightHours === 12,
  );
  await page
    .getByRole("slider", { name: "Photoperiod", exact: true })
    .fill("12");
  expect((await response).status()).toBe(200);
  await expect(
    page.getByRole("spinbutton", { name: "Photoperiod value" }),
  ).toHaveValue("12");
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Crop intelligence" }).click();
  await expect(
    page.getByRole("heading", { name: "Lettuce", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
test("comparison, evidence search, and processed measurement preview", async ({
  page,
}) => {
  await ready(page, "comparison");
  await expect(
    page.getByRole("heading", { name: "Custom habitat", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Matched growth trajectories" }),
  ).toBeVisible();
  await ready(page, "datasets");
  await page
    .getByRole("searchbox", { name: "Search NASA datasets" })
    .fill("OSD-655");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("button", { name: "Details", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: /mizuna_harvest.csv/ }),
  ).toBeVisible();
  await expect(
    page.getByText("harvestFreshMassG", { exact: true }),
  ).toBeVisible();
});
test("saved models use real artifacts and reject unsupported scientific scope", async ({
  page,
}) => {
  await ready(page, "predictions");
  await expect(
    page.getByRole("heading", { name: "Mizuna harvest experiment" }),
  ).toBeVisible();
  await expect(page.getByText(/R2: -0.153/)).toBeVisible();
  await page
    .getByRole("button", { name: "Run saved model", exact: true })
    .click();
  await expect(
    page.getByText("g fresh mass/pillow", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Load measured training example" })
    .click();
  await expect(page.getByText(/This is a training specimen/)).toBeVisible();
  await page
    .getByRole("button", { name: "Classify molecular context" })
    .click();
  await expect(
    page.getByText(/Uncalibrated flight probability:/),
  ).toBeVisible();
});
test("deterministic advisor, constrained optimization, exports and fallback", async ({
  page,
}, testInfo) => {
  await ready(page, "advisor");
  await expect(
    page.getByRole("heading", { name: "Training coverage", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Find trade-offs" }).click();
  await expect(page.getByText(/81 candidates evaluated/)).toBeVisible({
    timeout: 20000,
  });
  await page.getByRole("button", { name: "Apply recommendation" }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Applied the exploratory recommendation" }),
  ).toBeVisible();
  await ready(page, "analytics");
  for (const format of ["CSV", "JSON", "PDF"]) {
    const download = page.waitForEvent("download");
    await page
      .getByRole("button", { name: `Download ${format}`, exact: true })
      .click();
    expect((await download).suggestedFilename()).toContain(
      `.${format.toLowerCase()}`,
    );
  }
  await page
    .getByRole("button", { name: "Save scenario", exact: true })
    .click();
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await page.getByRole("textbox", { name: "Email" }).fill(`scenario-${testInfo.project.name}-${Date.now()}@example.test`);
  await page.getByRole("textbox", { name: "Password" }).fill("CorrectHorseBattery1!");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByText(/Your scenarios are private/)).toBeVisible();
  await page.getByRole("button", { name: "Save scenario", exact: true }).click();
  await expect(
    page.getByText("Scenario saved to mission history."),
  ).toBeVisible();
  await ready(page, "greenhouse");
  const viewToggle = page.getByRole("switch");
  if ((await viewToggle.getAttribute("aria-checked")) === "true")
    await viewToggle.click();
  await expect(
    page.getByRole("img", { name: "Schematic of the growth chamber" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "water", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: /Supplied.*recovered/ }),
  ).toBeVisible();
});
test("API outages are explicit and retry recovers", async ({ page }) => {
  await page.route("**/api/simulate", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Test backend unavailable" }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText(
    "Test backend unavailable",
  );
  await expect(page.locator(".metric-value").first()).toContainText("—");
  await page.unroute("**/api/simulate");
  await page.getByRole("button", { name: "Retry connection" }).click();
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
});
