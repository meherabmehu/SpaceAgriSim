import { test, expect } from "@playwright/test";

// The two Phase 9 NASA OSD-46 classifiers are served through the existing
// prediction card pattern on the predictions page. These tests check the things
// that actually matter to a reader: that the endpoints answer, that a centroid is
// labelled synthetic rather than passed off as a specimen, and that the accuracy
// claim arrives with its confound and its permutation p-value attached.

const CARDS = [
  { title: "Radiation quality response", model: "radiation-quality-osd46-v1" },
  { title: "Radiation exposure response", model: "radiation-exposure-osd46-v1" },
];

function card(page, title) {
  return page.locator(".mission-card").filter({ hasText: title });
}

test("radiation classifier cards answer and disclose their scope", async ({
  page,
}, testInfo) => {
  await page.goto("/#predictions");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();

  for (const { title, model } of CARDS) {
    const panel = card(page, title);
    await expect(panel).toBeVisible();
    // The classification claim and its provenance are visible before any click.
    await expect(panel).toContainText("OSD-46");

    const response = page.waitForResponse((r) =>
      r.url().includes(`/api/predict/${model}`),
    );
    await panel.getByRole("button", { name: /control centroid/i }).click();
    expect((await response).status()).toBe(200);

    // A centroid is synthetic and the page has to say so every time.
    await expect(panel).toContainText(/synthetic|average of the training/i);
    // The measured evaluation travels with the prediction.
    await expect(panel).toContainText(/balanced accuracy/i);
    await expect(panel).toContainText(/permutation p/i);
    await expect(panel).toContainText(/Cram/i);
    // The exclusion must be stated outright. Rather than pattern-matching a word
    // that legitimately appears inside its own disclaimer, every sentence that
    // mentions yield is checked to be a negation rather than a claim.
    await expect(panel).toContainText(/does not predict yield|never predicts yield/i);
    const yieldSentences = (await panel.evaluate((node) =>
      node.textContent.split(/(?<=[.;])\s+/),
    )).filter((sentence) => /yield/i.test(sentence));
    expect(yieldSentences.length).toBeGreaterThan(0);
    for (const sentence of yieldSentences) {
      expect(sentence).toMatch(/not|never|no such|cannot/i);
    }
    await expect(panel).not.toContainText(/g\/plant|kg\/m²/);

    // Captured so later phases can prove these cards did not drift. Written to the
    // gitignored output tree; the committed baseline is refreshed deliberately by
    // scripts/visual_regression.py --refresh and reviewed as a design change.
    await panel.screenshot({
      path: `test-results/screenshots/radiation-${testInfo.project.name}-${model}.png`,
    });
  }

  // Rendering the extra cards must not break the responsive layout.
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
});

test("the explanation is exact, disclosed, and closed until asked for", async ({
  page,
}) => {
  await page.goto("/#predictions");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();

  const panel = card(page, CARDS[0].title);
  // An explanation is of a specific input, so a prediction must exist first.
  await panel.getByRole("button", { name: /control centroid/i }).click();
  await expect(panel.getByRole("button", { name: /explain this prediction/i })).toBeVisible();
  // Closed by default: asking for an explanation is a deliberate act.
  await expect(panel).not.toContainText(/reconstruction residual/i);

  const response = page.waitForResponse((r) =>
    r.url().includes(`/api/models/${CARDS[0].model}/explanation`),
  );
  await panel.getByRole("button", { name: /explain this prediction/i }).click();
  expect((await response).status()).toBe(200);

  // The claim that matters: the numbers come from the served weights, not a surrogate.
  await expect(panel).toContainText(/not a surrogate|shipped weight vectors/i);
  await expect(panel).toContainText(/reconstruction residual/i);
  // Stability is part of the explanation, not an appendix to it.
  await expect(panel).toContainText(/held-out folds/i);
  await expect(panel).toContainText(/fewer than half the folds/i);
  // And it repeats its own limits.
  await expect(panel).toContainText(/not a causal claim|not a biomarker/i);

  // Collapsing restores the resting layout.
  await panel.getByRole("button", { name: /hide explanation/i }).click();
  await expect(panel).not.toContainText(/reconstruction residual/i);
});

test("every class centroid is classified as its own class", async ({ page }) => {
  await page.goto("/#predictions");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  const panel = card(page, "Radiation quality response");
  for (const label of ["control", "gamma", "hze"]) {
    const response = page.waitForResponse((r) =>
      r.url().includes("/api/predict/radiation-quality-osd46-v1"),
    );
    await panel.getByRole("button", { name: new RegExp(`${label} centroid`, "i") }).click();
    expect((await response).status()).toBe(200);
    await expect(panel.locator(".comparison-value")).toHaveText(
      new RegExp(label, "i"),
    );
  }
});

test("a rejected input surfaces the API error, not a silent success", async ({
  page,
}) => {
  // Feed the model a partial gene vector. The endpoint must refuse it, and the
  // UI must show the reason instead of a confident label.
  await page.route("**/api/predict/radiation-quality-osd46-v1", (route) =>
    route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify({
        detail: { error: "expression-feature-mismatch", missingGeneCount: 149 },
      }),
    }),
  );
  await page.goto("/#predictions");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  const panel = card(page, "Radiation quality response");
  await panel.getByRole("button", { name: /control centroid/i }).click();
  await expect(panel.getByRole("alert")).toBeVisible();
  await expect(panel.locator(".comparison-value")).toHaveCount(0);
});
