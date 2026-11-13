import { test, expect } from "@playwright/test";

/**
 * The three actions the page offers, driven the way a user drives them.
 *
 * Each of these was reported as "does not work", and in each case the honest failure was not an
 * exception in the console but a result the user could not use:
 *
 *  1. factor + band -> "Show measured results" answered 200 with raw band ids in the select and a
 *     95 % interval computed over two experiments;
 *  2. "Save scenario" wrote a row and said so in a notice at the top of a page whose button is at
 *     the bottom, showed no identifier, and let a second press write a twin;
 *  3. "Export mission" downloaded JSON under a filename the client invented, and offered no other
 *     format although the server renders PDF and CSV.
 *
 * These tests press the rendered controls at all three viewports and check what arrived in the
 * browser: an option label, a downloaded file, a saved id read back from the API.
 */

const PASSWORD = "CorrectHorseBattery1!";

async function apiSignIn(page, email) {
  const response = await page.request.post("/api/auth/register", {
    data: { email, password: PASSWORD },
  });
  expect(response.status()).toBe(201);
  const session = await response.json();
  await page.addInitScript((value) => {
    localStorage.setItem("spaceagrisim.auth", JSON.stringify(value));
  }, session);
  return session;
}

async function ready(page) {
  await page.goto("/#dashboard");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator(".simulation-content")).toHaveAttribute("aria-busy", "false");
}

async function openCea(page) {
  await page.goto("/#workflows");
  await expect(page.getByRole("heading", { name: "Guided scientific workflows" })).toBeVisible();
  await page.getByRole("tab", { name: /Controlled environment \(wheat\)/ }).click();
  await expect(page.getByRole("combobox", { name: "Band" })).toBeVisible();
}

async function readDownload(download) {
  const fs = await import("node:fs/promises");
  const path = await download.path();
  return fs.readFile(path);
}

test("every band is offered under the label the API derived from its bounds",
  async ({ page, request }) => {
    await openCea(page);
    const capability = await (await request.get(
      "/api/workflows/light-stress/controlled-environment/capability")).json();
    const labels = capability.fields[1].labels;

    const factor = page.getByRole("combobox", { name: "Factor" });
    const band = page.getByRole("combobox", { name: "Band" });
    for (const name of capability.fields[0].options) {
      await factor.selectOption(name);
      const offered = await band.locator("option").allInnerTexts();
      for (const bandId of capability.fields[1].options[name]) {
        // The option starts with the derived label; the experiment count may follow it.
        expect(offered.some((text) => text.startsWith(labels[name][bandId]))).toBe(true);
        // And the raw id is not what is shown: "ambient" alone was the bug.
        expect(offered).not.toContain(bandId);
      }
    }
  });

test("a value exactly on a band boundary is reported in that band", async ({ page, request }) => {
  await openCea(page);
  await page.getByRole("combobox", { name: "Factor" }).selectOption("airTemperatureC");
  await page.getByRole("combobox", { name: "Band" }).selectOption("cool");
  await page.getByRole("button", { name: /Show measured results/ }).click();
  await expect(page.getByRole("heading", { name: /3 · Measured results for that band/ }))
    .toBeVisible();

  const api = await (await request.post(
    "/api/workflows/light-stress/controlled-environment/run",
    { data: { selections: [{ factor: "airTemperatureC", band: "cool" }] } })).json();
  const group = api.groups[0];
  // The boundary experiments (23.0 °C, the band's upper edge) are inside the selection.
  expect(group.experiments).toContain("Exp002");
  expect(group.measured.n).toBe(group.experiments.length);
  await expect(page.locator(".workflow-panel table").last().locator("tbody tr").first())
    .toContainText(String(group.measured.n));
});

test("a band with too few experiments shows the count and declines the interval",
  async ({ page, request }) => {
    await openCea(page);
    await page.getByRole("combobox", { name: "Factor" }).selectOption("photoperiodHours");
    await page.getByRole("combobox", { name: "Band" }).selectOption("short");
    await page.getByRole("button", { name: /Show measured results/ }).click();
    const row = page.locator(".workflow-panel table").last().locator("tbody tr").first();
    await expect(row).toContainText("2");
    // No interval is fabricated at n = 2; the interval cell explains why instead.
    const intervalCell = row.locator("td").nth(2);
    await expect(intervalCell).toContainText(/needs at least 3/i);
    await expect(intervalCell).not.toContainText(/\d\.\d+\s*[–-]\s*\d/);

    const api = await (await request.post(
      "/api/workflows/light-stress/controlled-environment/run",
      { data: { selections: [{ factor: "photoperiodHours", band: "short" }] } })).json();
    expect(api.groups[0].measured.ciStatus).toBe("insufficient-observations");
  });

test("the measured band exports as a CSV file that contains the evidence",
  async ({ page }) => {
    await openCea(page);
    await page.getByRole("button", { name: /Show measured results/ }).click();
    await expect(page.getByRole("heading", { name: /3 · Measured results for that band/ }))
      .toBeVisible();

    const waiting = page.waitForEvent("download");
    await page.getByRole("button", { name: /Export band \(CSV\)/ }).click();
    const download = await waiting;
    expect(download.suggestedFilename()).toMatch(
      /^spaceagrisim-cea-wheat-co2Ppm-ambient-\d{8}\.csv$/);

    const text = (await readDownload(download)).toString("utf8");
    expect(text).toContain("10.5281/zenodo.17764612");
    expect(text).toContain("CC BY 4.0");
    expect(text).toContain("CO2 concentration ≤ 450 ppm");
    expect(text).toContain("Limitations");
    await expect(page.locator(".save-status").first()).toContainText(download.suggestedFilename());
  });

test("the measured band exports as a PDF file", async ({ page }) => {
  await openCea(page);
  await page.getByRole("button", { name: /Show measured results/ }).click();
  await expect(page.getByRole("heading", { name: /3 · Measured results for that band/ }))
    .toBeVisible();

  const waiting = page.waitForEvent("download");
  await page.getByRole("button", { name: /Export band \(PDF\)/ }).click();
  const download = await waiting;
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  const bytes = await readDownload(download);
  expect(bytes.subarray(0, 5).toString()).toBe("%PDF-");
  expect(bytes.length).toBeGreaterThan(1500);
});

test("saving a measured band stores it for the account that is signed in",
  async ({ page, request }) => {
    const session = await apiSignIn(page, `e2e-cea-save-${Date.now()}@example.com`);
    await openCea(page);
    await page.getByRole("button", { name: /Show measured results/ }).click();
    await expect(page.getByRole("heading", { name: /3 · Measured results for that band/ }))
      .toBeVisible();

    await page.getByRole("button", { name: /Save this measured band/ }).click();
    const status = page.locator(".save-status").first();
    await expect(status).toContainText(/Saved to your account as /);
    const id = (await status.innerText()).match(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/)?.[0];
    expect(id).toBeTruthy();

    // The id on screen is the row the server holds, with the band's context attached.
    const response = await request.get(`/api/scenarios/${id}`, {
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });
    expect(response.status()).toBe(200);
    const stored = await response.json();
    expect(stored.context.workflow).toBe("cea-evidence");
    expect(stored.context.band).toBe("ambient");
    expect(stored.context.bandLabel).toContain("450 ppm");
    expect(stored.context.measured.n).toBeGreaterThan(20);

    // A second press is the same scenario, not a second row.
    await page.getByRole("button", { name: /Save this measured band/ }).click();
    await expect(status).toContainText(/already saved as/);
    await expect(status).toContainText(id);

    // And it is on the account page, with the reading it recorded.
    await page.goto("/#account");
    const listed = page.locator(".scenario-list li", { hasText: stored.name });
    await expect(listed).toHaveCount(1);
    await expect(listed).toContainText(/Guided workflow record: cea-evidence/);
    await expect(listed).toContainText("≤ 450 ppm");
  });

test("a signed-out save asks for a sign-in and claims nothing was stored",
  async ({ page }) => {
    await page.addInitScript(() => localStorage.removeItem("spaceagrisim.auth"));
    await openCea(page);
    await page.getByRole("button", { name: /Show measured results/ }).click();
    await page.getByRole("button", { name: /Save this measured band/ }).click();
    const status = page.locator(".save-status").first();
    await expect(status).toContainText(/Sign in to save/);
    await expect(status).not.toContainText(/Saved to your account/);
  });

test("the mission exports a PDF and a CSV, named by the server",
  async ({ page }) => {
    await ready(page);

    const pdfWait = page.waitForEvent("download");
    await page.getByRole("button", { name: /Export mission \(PDF\)/ }).click();
    const pdf = await pdfWait;
    expect(pdf.suggestedFilename()).toBe("spaceagrisim-mission.pdf");
    expect((await readDownload(pdf)).subarray(0, 5).toString()).toBe("%PDF-");

    const csvWait = page.waitForEvent("download");
    await page.getByRole("button", { name: /Export mission \(CSV\)/ }).click();
    const csv = await csvWait;
    expect(csv.suggestedFilename()).toBe("spaceagrisim-mission.csv");
    const text = (await readDownload(csv)).toString("utf8");
    expect(text).toContain("day,standing_biomass_g");
    expect(text.toLowerCase()).toContain("not nasa validated");
  });

test("saving a mission scenario states the real identifier beside the button",
  async ({ page, request }) => {
    const session = await apiSignIn(page, `e2e-mission-save-${Date.now()}@example.com`);
    await ready(page);

    const save = page.getByRole("button", { name: /Save scenario/ });
    await save.scrollIntoViewIfNeeded();
    await save.click();

    const status = page.locator(".save-status").first();
    await expect(status).toBeVisible();
    await expect(status).toContainText(/Saved to your account as /);
    // The message is beside the button that produced it, not 1600 px above it.
    const statusBox = await status.boundingBox();
    const saveBox = await save.boundingBox();
    expect(Math.abs(statusBox.y - saveBox.y)).toBeLessThan(120);

    const id = (await status.innerText()).match(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/)?.[0];
    expect(id).toBeTruthy();

    const listing = await (await request.get("/api/scenarios", {
      headers: { Authorization: `Bearer ${session.accessToken}` },
    })).json();
    expect(listing.scenarios.map((row) => row.id)).toContain(id);

    // Pressing again does not write a second row.
    await save.click();
    await expect(status).toContainText(/already saved as/);
    const after = await (await request.get("/api/scenarios", {
      headers: { Authorization: `Bearer ${session.accessToken}` },
    })).json();
    expect(after.scenarios.length).toBe(1);
  });

test("a signed-out mission save offers sign-in instead of a fake success", async ({ page }) => {
  await page.addInitScript(() => localStorage.removeItem("spaceagrisim.auth"));
  await ready(page);
  const save = page.getByRole("button", { name: /Save scenario/ });
  await save.scrollIntoViewIfNeeded();
  await save.click();
  await expect(page.locator(".save-status").first()).toContainText(/Sign in to save/);
  await expect(page.getByRole("dialog")).toBeVisible();
});
