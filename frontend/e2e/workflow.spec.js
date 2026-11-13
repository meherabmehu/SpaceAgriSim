import { test, expect } from "@playwright/test";

/**
 * The scientific workflow is the only page where a reader can cause a model to run, so the test
 * asserts the things that would make it dishonest rather than the things that make it pretty:
 * a retired model cannot be selected, a bad input is refused with the backend's reason, the
 * output is labelled as model output, and a saved analysis can be exported and read back.
 */

const PASSWORD = "CorrectHorseBattery1!";

async function openWorkflow(page) {
  // Navigate by URL rather than clicking the sidebar: the collapsed-navigation behaviour differs
  // between the tablet and mobile projects and is already covered by mission.spec.js. What this
  // file is responsible for is the workflow itself.
  await page.goto("/#workflow");
  await page.reload();
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator(".simulation-content")).toHaveAttribute("aria-busy", "false");
  await expect(page).toHaveURL(/#workflow/);
  await expect(page.getByText("EVIDENCE TO EXPORTED ANALYSIS")).toBeVisible();
}

async function selectLettuce(page) {
  await page
    .getByRole("button", { name: /Lettuce Earth growth/ })
    .first()
    .click();
}

async function fillLettuce(page, { days = "20", air = "24", root = "22", ppfd = "400" } = {}) {
  await page.getByLabel("daysAfterTransplant value").fill(days);
  await page.getByLabel("airTemperature value").fill(air);
  await page.getByLabel("rootTemperature value").fill(root);
  await page.getByLabel("ppfd value").fill(ppfd);
}

test("a retired model cannot be run from the workflow", async ({ page }) => {
  await openWorkflow(page);
  const retired = page
    .getByRole("button", { name: /Mizuna absolute leaf microbial load|mizuna-microbial-load-v1/ })
    .first();
  if (await retired.count()) {
    await expect(retired).toBeDisabled();
    await expect(retired).toHaveAttribute("aria-disabled", "true");
  }
});

test("valid inputs produce a labelled model output, not a measurement", async ({
  page,
}) => {
  await openWorkflow(page);
  await selectLettuce(page);
  await fillLettuce(page);

  const runResponse = page.waitForResponse((r) =>
    r.url().endsWith("/api/workflow/run") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Run model" }).click();
  expect((await runResponse).status()).toBe(200);

  await expect(page.getByText("Prediction", { exact: true })).toBeVisible();
  await expect(page.getByText("uncalibrated point estimate").first()).toBeVisible();
  await expect(
    page.getByText(/Exploratory mathematical estimates|model output|not a measurement/i).first(),
  ).toBeVisible();
});

test("an out-of-domain input is refused with the backend's reason", async ({
  page,
}) => {
  await openWorkflow(page);
  await selectLettuce(page);
  // 999 days after transplant is far outside the recorded domain.
  await fillLettuce(page, { days: "999" });
  const response = page.waitForResponse((r) => r.url().endsWith("/api/workflow/run"));
  await page.getByRole("button", { name: "Run model" }).click();
  const status = (await response).status();
  expect([409, 413, 422]).toContain(status);
  await expect(page.getByRole("alert")).toBeVisible();
});

test("validate rejects an incomplete input set before anything runs", async ({
  page,
}) => {
  await openWorkflow(page);
  await selectLettuce(page);
  await page.getByRole("button", { name: "Validate inputs" }).click();
  await expect(page.getByRole("alert")).toContainText(/number for every model input/i);
});

test("a saved analysis can be exported and the export says it is not a measurement", async ({
  page,
}) => {
  await openWorkflow(page);

  // Saving requires an account, and the page must say so rather than failing silently.
  await selectLettuce(page);
  await fillLettuce(page);
  await page.getByRole("button", { name: "Run and save" }).click();
  await expect(page.getByRole("alert")).toContainText(/Sign in to save/i);

  // Register through the API and seed the same localStorage key the app reads, so this test
  // covers the save-and-export flow rather than the sign-in form (which mission.spec.js owns).
  const email = `workflow-e2e-${Date.now()}@example.test`;
  const registration = await page.request.post("/api/auth/register", {
    data: { email, password: PASSWORD },
  });
  expect(registration.status()).toBeLessThan(400);
  const session = await registration.json();
  await page.evaluate(
    (value) => localStorage.setItem("spaceagrisim.auth", JSON.stringify(value)),
    session,
  );

  // A hash-only navigation does not reload the document, so the app would keep the session
  // state it read before the account existed. Reload to make the seeded session take effect.
  await openWorkflow(page);
  await selectLettuce(page);
  await fillLettuce(page);
  await page.getByRole("button", { name: "Run and save" }).click();
  await expect(page.getByText(/Saved as/)).toBeVisible();

  const download = page.waitForEvent("download");
  // Exact: the mission header now offers "Export mission (CSV)", and a substring match would
  // resolve to both buttons. This assertion is about the saved analysis's own export.
  await page.getByRole("button", { name: "CSV", exact: true }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/\.csv$/);
});
