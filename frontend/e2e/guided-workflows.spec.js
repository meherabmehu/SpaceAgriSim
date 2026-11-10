import { test, expect } from "@playwright/test";

/**
 * The two guided workflows, driven the way a researcher would drive them, on three viewports.
 *
 * These are journeys, not smoke tests. Each test enters parameters through the rendered controls,
 * presses the run button, and then checks the numbers on screen against the same numbers the API
 * returns — which is the only way to know the page is showing the calculation rather than a
 * placeholder. The refusal paths are tested too: an unsupported crop and an out-of-domain
 * environment must produce a visible statement rather than a silently different number.
 */

/** Read a cell as a number, ignoring the thousands separators the page formats with. */
async function cellNumber(row, index) {
  const text = await row.locator("td").nth(index).innerText();
  return Number(text.replace(/,/g, "").trim());
}

async function openWorkflows(page, testInfo) {
  await page.goto("/#dashboard");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  // The navigation is a drawer on a phone, so it has to be opened before the link exists.
  if (testInfo?.project?.name === "mobile")
    await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Guided workflows" }).click();
  await expect(page.getByRole("heading", { name: "Guided scientific workflows" })).toBeVisible();
}

async function openHarvest(page, testInfo) {
  await openWorkflows(page, testInfo);
  await page.getByRole("tab", { name: /Crop growth & harvest/ }).click();
  await expect(page.getByRole("heading", { name: "1 · Growth stage and environment" })).toBeVisible();
}

test("water demand workflow runs from the page and matches the API", async ({ page, request }, testInfo) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await openWorkflows(page, testInfo);
  await expect(page.getByRole("heading", { name: "1 · Choose the crop and the site" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Dhaka, March" })).toBeVisible();

  await page.getByRole("button", { name: /Run water demand/ }).click();
  await expect(page.getByRole("heading", { name: "2 · Results and scenario comparison" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "3 · The measured evidence, beside the estimate" })).toBeVisible();

  // The table must carry the API's numbers, not its own arithmetic.
  const api = await request.post("/api/workflows/water-demand/run", {
    data: {
      scenarios: [
        {
          label: "Dhaka, March", crop: "lettuce", growingAreaM2: 10, daysAfterTransplant: 20,
          tmaxC: 33, tminC: 22, relativeHumidityPct: 55, solarRadiationMJm2: 20, windSpeedMs: 2,
          dayOfYear: 80, latitude: 23.8, elevationM: 8, plantsPerM2: 25,
        },
        {
          label: "Hot dry spell", crop: "lettuce", growingAreaM2: 10, daysAfterTransplant: 20,
          tmaxC: 38, tminC: 27, relativeHumidityPct: 35, solarRadiationMJm2: 26, windSpeedMs: 3.5,
          dayOfYear: 80, latitude: 23.8, elevationM: 8, plantsPerM2: 25,
        },
      ],
    },
  });
  expect(api.status()).toBe(200);
  const body = await api.json();
  const first = body.scenarios[0].demand.et0Reference.litresPerDay;

  const rows = page.locator(".workflow-panel table").first().locator("tbody tr");
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toContainText("penman-monteith");
  await expect(page.getByText(/unarbitrated/)).toBeVisible();
  // Every number on the page came from the API. The page rounds for display, so the check is
  // numeric and tolerant rather than a string match on the unrounded payload.
  const shown = await cellNumber(rows.first(), 2);
  expect(shown).toBeCloseTo(first, 1);

  // The measured bench is labelled as measured, with its DOI and hash state.
  await expect(page.getByText(/10\.5281\/zenodo\.5550230/).first()).toBeVisible();
  await expect(page.getByText(/Source hash verified/)).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "reference-calculation" })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "measured-observation" }).first()).toBeVisible();

  await testInfo.attach("water-demand-results", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
  expect(errors).toEqual([]);
});

test("water demand comparison between two scenarios is shown with deltas", async ({ page }, testInfo) => {
  await openWorkflows(page, testInfo);
  await page.getByRole("button", { name: /Run water demand/ }).click();
  await expect(page.getByRole("heading", { name: "2 · Results and scenario comparison" })).toBeVisible();

  // The second scenario is hotter and drier, so its ET0-reference demand must be larger.
  const rows = page.locator(".workflow-panel table").first().locator("tbody tr");
  const firstDemand = await cellNumber(rows.nth(0), 2);
  const secondDemand = await cellNumber(rows.nth(1), 2);
  expect(secondDemand).toBeGreaterThan(firstDemand);

  // The delta table names the baseline and gives a percentage.
  await expect(page.getByText(/Hot dry spell vs Dhaka, March/)).toBeVisible();
  await expect(page.getByText(/Negative demand deltas mean/).first()).toBeVisible();
});

test("water demand refuses a crop it has no measurement for", async ({ page }, testInfo) => {
  await openWorkflows(page, testInfo);
  await page.getByRole("combobox", { name: "Crop", exact: true }).selectOption("tomato");
  await page.getByRole("button", { name: /Run water demand/ }).click();
  await expect(page.getByText(/There is no measurement for tomato/).first()).toBeVisible();
  // The computed demand is still shown: only the measurement is withheld.
  await expect(page.getByRole("heading", { name: "3 · The measured evidence, beside the estimate" })).toBeVisible();
});

test("harvest workflow runs the model and shows the interval and the failed holdout", async ({ page, request }, testInfo) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await openHarvest(page, testInfo);
  await expect(page.getByText(/model status: trained-exploratory/)).toBeVisible();

  await page.getByRole("button", { name: /Run harvest prediction/ }).click();
  await expect(page.getByRole("heading", { name: "2 · Results" })).toBeVisible();
  await expect(page.getByText("holdout failed · not a forecast")).toBeVisible();

  const api = await request.post("/api/workflows/harvest-prediction/run", {
    data: {
      scenarios: [
        { label: "Plant factory, 16 h", daysAfterTransplant: 21, airTemperature: 24, rootTemperature: 24, ppfd: 400, photoperiodHours: 16, plantDensityPerM2: 25 },
        { label: "Shorter photoperiod, 12 h", daysAfterTransplant: 21, airTemperature: 24, rootTemperature: 24, ppfd: 400, photoperiodHours: 12, plantDensityPerM2: 25 },
      ],
    },
  });
  expect(api.status()).toBe(200);
  const body = await api.json();
  const baseline = body.scenarios[0].prediction.freshShootMassGPerPlant;

  const rows = page.locator(".workflow-panel table").first().locator("tbody tr");
  await expect(rows).toHaveCount(2);
  const shownBaseline = await cellNumber(rows.first(), 2);
  expect(shownBaseline).toBeCloseTo(baseline, 1);

  // The photoperiod control genuinely changed the answer: the shorter day gives less mass.
  const shorter = await cellNumber(rows.nth(1), 2);
  expect(shorter).toBeLessThan(baseline);

  // The independent holdout is reported as failed, with the criterion it failed.
  await expect(page.getByText(/Independent holdout, Touliatos 2016/)).toBeVisible();
  await expect(page.getByText("failed", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/development · not counted/).first()).toBeVisible();

  await testInfo.attach("harvest-results", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
  expect(errors).toEqual([]);
});

test("harvest workflow flags an environment outside the measured domain", async ({ page }, testInfo) => {
  await openHarvest(page, testInfo);
  const air = page.getByRole("spinbutton", { name: "Air temperature", exact: true });
  await air.fill("35");
  await air.blur();
  await page.getByRole("button", { name: /Run harvest prediction/ }).click();
  await expect(page.getByRole("heading", { name: "2 · Results" })).toBeVisible();
  await expect(page.getByText(/outside the measured training range/).first()).toBeVisible();
});

test("harvest workflow adds a third scenario and compares it", async ({ page }, testInfo) => {
  await openHarvest(page, testInfo);
  await page.getByRole("button", { name: /Add scenario/ }).click();
  await expect(page.getByRole("tab", { name: /Scenario 3/ })).toBeVisible();
  const densityFields = page.getByRole("spinbutton", { name: "Planting density", exact: true });
  await densityFields.last().fill("50");
  await page.getByRole("button", { name: /Run harvest prediction/ }).click();
  const rows = page.locator(".workflow-panel table").first().locator("tbody tr");
  await expect(rows).toHaveCount(3);
  await expect(page.getByText(/vs Plant factory, 16 h/)).toHaveCount(2);
});
