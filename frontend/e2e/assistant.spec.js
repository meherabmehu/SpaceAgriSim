import { test, expect } from "@playwright/test";

async function ready(page, hash) {
  await page.goto(`/#${hash}`);
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.locator(".simulation-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
}

async function openPage(page, hash, testInfo) {
  await ready(page, "dashboard");
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Research assistant" }).click();
  await expect(page).toHaveURL(new RegExp(`#${hash}`));
}

test("the research assistant answers with citations it actually retrieved", async ({
  page,
}, testInfo) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await openPage(page, "assistant", testInfo);

  const response = page.waitForResponse((r) =>
    r.url().endsWith("/api/assistant/ask"),
  );
  await page
    .getByRole("searchbox", { name: "Ask a question about the repository evidence" })
    .fill("Is OSD-320 an independent replication of OSD-46?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  expect((await response).status()).toBe(200);

  // Grounded answers must be cited, and the citation must name the accession.
  await expect(page.locator(".citation-list > li").first()).toBeVisible();
  await expect(
    page.locator(".citation-list").getByText(/OSD-(46|320)/).first(),
  ).toBeVisible();
  await expect(page.getByText(/GROUNDING · GROUNDED/i)).toBeVisible();
  await expect(page.locator(".claim-list li").first()).toBeVisible();
  await expect(
    page.getByText("Measured data versus model interpretation"),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("a question outside the corpus is refused instead of answered", async ({
  page,
}, testInfo) => {
  await openPage(page, "assistant", testInfo);

  await page
    .getByRole("searchbox", { name: "Ask a question about the repository evidence" })
    .fill("How do I bake sourdough bread?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();

  await expect(page.getByText(/GROUNDING · INSUFFICIENT/i)).toBeVisible();
  await expect(page.getByText("Refused", { exact: true })).toBeVisible();
  // A refusal must not smuggle in citations that were never retrieved.
  await expect(page.locator(".citation-list > li")).toHaveCount(0);
});

test("the dataset explorer refuses to present OSD-320 as a second study", async ({
  page,
}, testInfo) => {
  await ready(page, "dashboard");
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "NASA data explorer" }).click();

  await expect(
    page.getByRole("heading", { name: "How many studies is that, really?" }),
  ).toBeVisible();
  await expect(page.getByText(/second deposit of OSD-46/).first()).toBeVisible();

  await page.getByRole("button", { name: "OSD-320", exact: true }).click();
  await page.getByRole("button", { name: "OSD-46", exact: true }).click();
  await page.getByRole("button", { name: "Check independence" }).click();
  await expect(page.getByText("Requested → independent")).toBeVisible();
  await expect(page.getByText("OSD-320 dropped · duplicate-measurement")).toBeVisible();
});

test("model cards state classification, calibration and retirement", async ({
  page,
}, testInfo) => {
  await ready(page, "dashboard");
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "AI prediction center" }).click();

  await expect(
    page.getByRole("heading", { name: "Scientific status of every served model" }),
  ).toBeVisible();
  await expect(page.getByText("retired", { exact: true })).toBeVisible();
  await expect(page.getByText(/Calibrated probabilities/).first()).toBeVisible();
});
