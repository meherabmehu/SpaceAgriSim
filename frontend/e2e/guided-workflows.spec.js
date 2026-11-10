import { test, expect } from "@playwright/test";

/**
 * The guided workflows as Phase 30 left them: two run end to end, one is a measured panel, and the
 * harvest tab is an evidence-only tombstone with no run control at all.
 *
 * These are journeys, not smoke tests. Each test enters parameters through the rendered controls,
 * presses the run button, and then checks the numbers on screen against the same numbers the API
 * returns — which is the only way to know the page is showing the calculation rather than a
 * placeholder. The refusal paths are tested too: an unsupported crop and an out-of-domain
 * environment must produce a visible statement rather than a silently different number.
 */

/**
 * Read a cell as a number, ignoring the thousands separators the page formats with.
 *
 * Some cells carry a second quantity after the first ("44.38 ± 13.14"), so the first numeric token
 * is what is read; a cell that contains no number at all returns NaN and the assertion says so.
 */
async function cellNumber(row, index) {
  const text = await row.locator("td").nth(index).innerText();
  const match = text.replace(/,/g, "").match(/-?\d+(\.\d+)?/);
  return match ? Number(match[0]) : NaN;
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
  await page.getByRole("tab", { name: /Harvest evidence \(removed\)/ }).click();
  await expect(page.getByRole("heading", { name: /1 · What this workflow was, and why it is gone/ }))
    .toBeVisible();
}

async function openCea(page, testInfo) {
  await openWorkflows(page, testInfo);
  await page.getByRole("tab", { name: /Controlled environment \(wheat\)/ }).click();
  await expect(page.getByRole("heading", { name: /1 · Pick an environmental factor and a band/ }))
    .toBeVisible();
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

test("harvest tab states the removal, shows every failed evaluation and offers no run control",
  async ({ page, request }, testInfo) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));

    await openHarvest(page, testInfo);

    // The decision is stated before any table, and there is nothing to press.
    await expect(page.getByText("removed in Phase 30 · no forecast is served")).toBeVisible();
    await expect(page.getByRole("button", { name: /Run harvest/i })).toHaveCount(0);
    await expect(page.getByRole("spinbutton")).toHaveCount(0);

    // The validation record carries the independent evaluations and their failed verdicts.
    await expect(page.getByRole("heading", { name: /2 · Every evaluation/ })).toBeVisible();
    const evaluations = page.locator(".workflow-panel table").first().locator("tbody tr");
    await expect(evaluations).not.toHaveCount(0);
    await expect(page.getByText("failed", { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/not scored/).first()).toBeVisible();

    // And the API agrees that the capability is gone: the run endpoint is a formal tombstone.
    const capability = await (await request.get("/api/workflows/harvest-prediction/capability")).json();
    expect(capability.status).toBe("unavailable");
    expect(capability.operationalForecast).toBe(false);
    const removed = await request.post("/api/workflows/harvest-prediction/run", { data: { scenarios: [] } });
    expect(removed.status()).toBe(410);

    // The parity table on screen is the API's parity table, not a redrawn one.
    const parity = await (await request.get("/api/workflows/harvest-prediction/parity")).json();
    const points = page.locator(".workflow-panel table").nth(1).locator("tbody tr");
    await expect(points).toHaveCount(parity.points.length);
    const shownRatio = await cellNumber(points.first(), 3);
    expect(shownRatio).toBeCloseTo(parity.points[0].ratio, 1);

    await testInfo.attach("harvest-evidence", {
      body: await page.screenshot({ fullPage: true }),
      contentType: "image/png",
    });
    expect(errors).toEqual([]);
  });

test("controlled-environment panel reports the measured band and matches the API",
  async ({ page, request }, testInfo) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));

    await openCea(page, testInfo);
    await expect(page.getByText(/measured · no prediction/)).toBeVisible();
    // The attempted response surface is disclosed as not served, above the results.
    await expect(page.getByText(/not served/).first()).toBeVisible();

    await page.getByRole("button", { name: /Show measured results/ }).click();
    await expect(page.getByRole("heading", { name: /3 · Measured results for that band/ })).toBeVisible();

    const api = await request.post("/api/workflows/light-stress/controlled-environment/run", {
      data: { selections: [{ factor: "co2Ppm", band: "ambient" }] },
    });
    expect(api.status()).toBe(200);
    const body = await api.json();
    const group = body.groups[0];

    const row = page.locator(".workflow-panel table").last().locator("tbody tr").first();
    await expect(page.locator(".workflow-panel table").last().locator("tbody tr"))
      .toHaveCount(body.groups.length);
    expect(await cellNumber(row, 0)).toBe(group.measured.n);
    expect(await cellNumber(row, 1)).toBeCloseTo(group.measured.mean, 3);

    // Nothing on the page may offer a prediction for a factor the data cannot support.
    await expect(page.getByRole("button", { name: /predict/i })).toHaveCount(0);

    await testInfo.attach("cea-measured", {
      body: await page.screenshot({ fullPage: true }),
      contentType: "image/png",
    });
    expect(errors).toEqual([]);
  });

test("the harvest tombstone behaves on a phone viewport", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "desktop and tablet are covered above");
  await openHarvest(page, testInfo);
  await expect(page.getByText("removed in Phase 30 · no forecast is served")).toBeVisible();
  await expect(page.getByRole("button", { name: /Run harvest/i })).toHaveCount(0);
});

/* ------------------------------------------------ light quality & stress (Phase 29) */

async function openLightStress(page, testInfo) {
  await openWorkflows(page, testInfo);
  await page.getByRole("tab", { name: /Light quality & stress/ }).click();
  await expect(page.getByRole("heading", { name: "1 · Choose the regimes to compare" }))
    .toBeVisible();
}

test("light stress workflow reports measured groups and matches the API", async ({ page, request }, testInfo) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await openLightStress(page, testInfo);
  // The panel must say what it is before the user reads any number.
  await expect(page.getByText(/Measured, not simulated/)).toBeVisible();

  await page.getByRole("button", { name: /Compare regimes/ }).click();
  await expect(page.getByRole("heading", { name: "2 · Measured means and spread" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "3 · Evidence, conditions and what is not supported" }))
    .toBeVisible();

  const api = await request.post("/api/workflows/light-stress/run", {
    data: {
      scenarios: [
        { label: "Control", regime: "control", daysAfterSowing: 35,
          traits: ["freshWeightG", "fvPOverFmP", "phiNO"] },
        { label: "T2 · increasing green", regime: "t2", daysAfterSowing: 35,
          traits: ["freshWeightG", "fvPOverFmP", "phiNO"] },
      ],
    },
  });
  expect(api.status()).toBe(200);
  const body = await api.json();
  const controlFresh = body.comparison.rows
    .find((row) => row.regime === "control" && row.trait === "freshWeightG");

  const rows = page.locator(".workflow-panel table").first().locator("tbody tr");
  await expect(rows).toHaveCount(body.comparison.rows.length);
  // Cells only: trait, n, mean, interval, day. The mean is the third cell; the page rounds for
  // display, so the check is numeric rather than a string match.
  const shown = await cellNumber(rows.first(), 2);
  expect(shown).toBeCloseTo(controlFresh.mean, 1);

  // Provenance is on the page, not only in the payload.
  await expect(page.getByText(/10\.5281\/zenodo\.20394352/).first()).toBeVisible();
  await expect(page.getByText(/CC BY 4\.0/).first()).toBeVisible();
  await expect(page.getByText(/Raw file SHA-256 verified/)).toBeVisible();
  await expect(page.getByText("no", { exact: true }).first()).toBeVisible();
  // No composite stress score is offered, and the page says why.
  await expect(page.getByText(/Composite stress score/)).toBeVisible();

  // The stress panel is taller than the mobile viewport's capture ceiling, so the phone screenshot
  // is the visible viewport rather than the whole page.
  await testInfo.attach("light-stress-results", {
    body: await page.screenshot({ fullPage: testInfo.project.name !== "mobile" }),
    contentType: "image/png",
  });
  expect(errors).toEqual([]);
});

test("light stress comparison separates the signals that held and the one that did not", async ({ page }, testInfo) => {
  await openLightStress(page, testInfo);
  await page.getByRole("button", { name: /Compare regimes/ }).click();
  await expect(page.getByRole("heading", { name: "2 · Measured means and spread" })).toBeVisible();
  // A delta table with the overlap verdict, and at least one pair of intervals that overlaps.
  await expect(page.getByText(/Difference from the control/)).toBeVisible();
  await expect(page.getByText(/T2 · increasing green vs/).first()).toBeVisible();
  await expect(page.getByText("no", { exact: true }).first()).toBeVisible();
});

test("light stress flags the regime that changes two things at once", async ({ page }, testInfo) => {
  await openLightStress(page, testInfo);
  await page.getByRole("combobox", { name: /Regime for Control/ }).selectOption("t3");
  await page.getByRole("button", { name: /Compare regimes/ }).click();
  await expect(page.getByRole("heading", { name: "2 · Measured means and spread" })).toBeVisible();
  // The confound is stated in the evidence notes, which are collapsed until opened.
  await page.getByText(/Evidence notes/).first().click();
  await expect(page.getByText(/t3 changes two things at once/).first()).toBeVisible();
});

test("light stress lets traits be turned off and adds a third regime", async ({ page }, testInfo) => {
  await openLightStress(page, testInfo);
  const chips = page.locator(".workflow-chip");
  await expect(chips.first()).toBeVisible();
  await page.getByRole("checkbox", { name: /Fresh weight/ }).uncheck();
  await page.getByRole("button", { name: /Add regime/ }).click();
  await page.getByRole("button", { name: /Compare regimes/ }).click();
  await expect(page.getByRole("heading", { name: "2 · Measured means and spread" })).toBeVisible();
  const rows = page.locator(".workflow-panel table").first().locator("tbody tr");
  const count = await rows.count();
  // Three regimes x two remaining traits.
  expect(count).toBe(6);
  // The deselected trait is gone from the results table, not merely dimmed in the picker.
  await expect(page.locator(".workflow-panel table").first()).not.toContainText("Fresh weight");
});
