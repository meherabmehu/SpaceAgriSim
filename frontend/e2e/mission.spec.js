import { test, expect } from "@playwright/test";
import { settleForCapture } from "./settle.js";



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
  // Captured into the gitignored test-results tree, not over the committed
  // baselines in docs/screenshots. Writing over the baseline would make the
  // visual regression gate compare a file against itself and always pass.
  await settleForCapture(page);
  await page.screenshot({
    path: `test-results/screenshots/mission-${testInfo.project.name}.png`,
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
  // Scoped to the study catalogue itself. This page carries four tables, and an
  // unscoped `tbody tr` also counts the rows other panels render once their own
  // fetches land - which made the assertion depend on which request finished
  // first rather than on the filter. Naming the table keeps the intent (the
  // catalogue filters to exactly one row) and removes that race.
  const catalog = page.getByRole("table", { name: "Study catalog" });
  await expect(catalog.locator("tbody tr")).toHaveCount(1);
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
  // Phase 31 removed the mizuna harvest form: the model was worse than predicting the training
  // mean (held-out R2 -0.333 against -0.138) and was withdrawn from every served surface. The
  // prediction centre must therefore offer no harvest control at all, and the models it does list
  // must be ones the API still serves.
  await expect(
    page.getByRole("heading", { name: "Mizuna harvest experiment" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run saved model" })).toHaveCount(0);
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
  // The confirmation states the identifier the database assigned, and it is rendered beside the
  // button rather than in the notice at the top of the page.
  await expect(
    page.locator(".save-status").filter({ hasText: /Saved to your account as / }),
  ).toBeVisible();
  await expect(page.locator(".save-status").first()).toContainText(
    /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
  );
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
// Phase 33 replaced the three.js chamber with a plain-SVG chamber view. This covers the
// interactions the 3D scene provided: orbit, zoom, reset, keyboard, system inspection and the
// chamber/schematic switch. The existing 2D-schematic assertions above still apply.
test("growth chamber view orbits, zooms, resets and inspects systems", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await ready(page, "greenhouse");
  const toggle = page.getByRole("switch");
  const chamber = page.getByRole("img", {
    name: "Isometric view of the growth chamber",
  });
  // a stored preference can leave the panel in schematic mode
  if ((await toggle.getAttribute("aria-checked")) !== "true")
    await toggle.click();
  await expect(chamber).toBeVisible();

  // the projection is a pure function of azimuth/elevation/zoom, so a changed frame geometry
  // proves the view actually moved rather than only re-rendering
  const frame = chamber.locator("polygon").first();
  const home = await frame.getAttribute("points");
  expect(home).toBeTruthy();

  await page.getByRole("button", { name: "Rotate view right" }).click();
  await expect.poll(() => frame.getAttribute("points")).not.toBe(home);

  const orbited = await frame.getAttribute("points");
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect.poll(() => frame.getAttribute("points")).not.toBe(orbited);

  await page.getByRole("button", { name: "Reset view" }).click();
  await expect.poll(() => frame.getAttribute("points")).toBe(home);

  // keyboard orbit: the svg is focusable and implements arrow keys
  await chamber.focus();
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => frame.getAttribute("points")).not.toBe(home);
  await page.keyboard.press("Home");
  await expect.poll(() => frame.getAttribute("points")).toBe(home);

  // inspecting a system swaps the legend text; these are the configured setpoints, not sensors
  await page.getByRole("button", { name: "lighting", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: /PPFD \d+ µmol\/m²\/s/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "sensors", exact: true }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: /configured setpoints, not sensor measurements/ }),
  ).toBeVisible();

  // switching to the schematic and back keeps both views working
  await toggle.click();
  await expect(
    page.getByRole("img", { name: "Schematic of the growth chamber" }),
  ).toBeVisible();
  await toggle.click();
  await expect(chamber).toBeVisible();
  expect(errors).toEqual([]);
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
