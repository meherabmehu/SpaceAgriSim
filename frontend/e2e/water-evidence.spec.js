import { test, expect } from "@playwright/test";

/**
 * The measured water-use panel, in the lab, across three viewports.
 *
 * The panel is the user-visible half of the water-use feature, so the browser test is not a smoke
 * test: it asserts the scientific content a user is expected to read - the verdict, the rank
 * agreement, the between-pot spread, the provenance - and it asserts that switching crop makes the
 * panel refuse to extrapolate rather than silently showing a lettuce number for tomato.
 */

async function openLab(page) {
  await page.goto("/#dashboard");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator(".simulation-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await page.getByRole("button", { name: "Open simulation lab" }).click();
  await expect(
    page.getByRole("heading", { name: "Habitat parameters" }),
  ).toBeVisible();
}

test("measured water-use panel shows the benchmark, the verdict and its provenance", async ({
  page,
}, testInfo) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));

  // Armed before the lab opens: the panel fetches on mount, so a listener registered after the
  // click races the request it is waiting for.
  const benchmarkResponse = page.waitForResponse((r) =>
    r.url().endsWith("/api/water-use-evidence"),
  );
  const compareResponse = page.waitForResponse((r) =>
    r.url().endsWith("/api/water-use-evidence/compare"),
  );

  await openLab(page);

  await expect(
    page.getByRole("heading", { name: "Measured water use" }),
  ).toBeVisible();

  expect((await benchmarkResponse).status()).toBe(200);
  expect((await compareResponse).status()).toBe(200);

  // The verdict is deliberately not a green tick.
  await expect(
    page.getByText("Shape supported · level not identified"),
  ).toBeVisible();
  // Rank agreement is shown with the number of dates it came from: 11.
  await expect(page.getByText(/Rank agreement across 11 dates/)).toBeVisible();
  await expect(page.getByText(/ρ = 0\.79/)).toBeVisible();
  // The measured spread is labelled as a spread, in per cent.
  await expect(page.getByText(/Measured between-pot spread/)).toBeVisible();
  await expect(page.getByText("Level inside that spread?")).toBeVisible();

  // Provenance travels with the numbers.
  await expect(
    page.getByText(/10\.5281\/zenodo\.5550230/),
  ).toBeVisible();
  await expect(page.getByText(/hash-verified/)).toBeVisible();

  // The chart is announced to assistive technology with its actual meaning.
  await expect(
    page.getByRole("img", {
      name: /Measured greenhouse lettuce water use against the platform demand curve/,
    }),
  ).toBeVisible();

  expect(errors).toEqual([]);
  await page.screenshot({
    path: `test-results/screenshots/water-evidence-${testInfo.project.name}.png`,
    fullPage: true,
  });
});

test("water panel refuses to extrapolate to a crop with no measurement", async ({
  page,
}) => {
  await openLab(page);
  await expect(
    page.getByRole("heading", { name: "Measured water use" }),
  ).toBeVisible();

  const switched = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/water-use-evidence/compare") &&
      r.request().postDataJSON().crop === "tomato",
  );
  await page.getByLabel("Crop").selectOption("tomato");
  await switched;

  await expect(
    page.getByText("No measurement exists for tomato."),
  ).toBeVisible();
  await expect(
    page.getByText(/none is extrapolated from the lettuce trial/),
  ).toBeVisible();
  // The comparison numbers must be gone, not left over from lettuce.
  await expect(page.getByText("Platform ÷ measured")).toHaveCount(0);
});

test("changing the light scale moves the platform curve and not the measurement", async ({
  page,
}) => {
  await openLab(page);
  const measured = page.getByText(/Measured over the trial/);
  await expect(measured).toBeVisible();
  const before = await page
    .locator(".stat-pair", { hasText: "Measured over the trial" })
    .locator("strong")
    .innerText();

  const beforeRatio = await page
    .locator(".stat-pair", { hasText: "Platform ÷ measured" })
    .locator("strong")
    .innerText();

  const replied = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/water-use-evidence/compare") &&
      r.request().postDataJSON().lightScale === 2,
  );
  // The numeric field, not the range: a range input cannot be filled reliably across engines.
  await page.getByLabel("Light scale for the water comparison value").fill("2");
  const payload = await (await replied).json();

  const after = await page
    .locator(".stat-pair", { hasText: "Measured over the trial" })
    .locator("strong")
    .innerText();
  expect(after).toBe(before);

  // The platform side must move, and it must move while the measurement does not.
  const afterRatio = await page
    .locator(".stat-pair", { hasText: "Platform ÷ measured" })
    .locator("strong")
    .innerText();
  expect(afterRatio).not.toBe(beforeRatio);
  expect(payload.uncertainty.withinMeasuredSpread).toBe(false);
  expect(payload.totals.measuredMlPerPot).toBeGreaterThan(0);
  expect(payload.totals.simulatedMlPerPot / payload.totals.simulatedOverMeasured).toBeCloseTo(
    payload.totals.measuredMlPerPot,
    0,
  );
});

test("water panel stays inside the viewport on every project", async ({ page }) => {
  await openLab(page);
  await expect(
    page.getByRole("heading", { name: "Measured water use" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
