import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 12000 },
  reporter: [["list"], ["html", { open: "never" }]],
  // Test artefacts live outside the repository tree by default.
  //
  // Playwright writes `.last-run` and per-test JSON into its output directory; keeping that
  // inside the checkout meant a test run left JSON files in the project. Pointing the default
  // at a temp directory means running the suite cannot deposit a JSON document in the repo,
  // while CI overrides PLAYWRIGHT_OUTPUT_DIR so the evidence it uploads still has a path.
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR || "/tmp/spaceagrisim-playwright",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // Rasterisation, pinned. The visual gate compares pixels, and FreeType picks its hinting and
    // subpixel strategy partly from what fontconfig finds installed, so the same page photographed
    // on a host with only DejaVu and on a host with Noto and Liberation came out 0.1-4 % different
    // with identical glyph outlines. These flags make the rendering a property of the browser
    // build rather than of the machine's font packages, which is the only way a pixel comparison
    // can mean "the page did not change".
    launchOptions: {
      args: [
        "--font-render-hinting=none",
        "--disable-font-subpixel-positioning",
        "--disable-lcd-text",
        // /dev/shm is 64 MB on a stock container; Chromium puts renderer shared memory there
        // and a long mobile page can exhaust it, which crashes the renderer rather than
        // failing an assertion. The flag moves that allocation to /tmp. It changes where
        // memory lives, not what is drawn.
        "--disable-dev-shm-usage",
        // A single renderer process bounds the memory a full-page capture of a long mobile
        // page can need. Software rasterisation is what headless already uses, so the pixels
        // are unchanged; this only stops a second renderer from competing for the budget.
        "--renderer-process-limit=1",
      ],
    },
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1100 },
      },
    },
    {
      name: "tablet",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 820, height: 1180 },
      },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      // Resolve the interpreter cross-platform instead of hard-coding a Windows
      // venv path, so the suite runs on Linux/macOS CI as well as on Windows.
      // PYTHON env var wins if the operator needs to point at a specific venv.
      command: `${process.env.PYTHON || (process.platform === "win32" ? "..\\\\backend\\\\.venv\\\\Scripts\\\\python.exe" : "python3")} -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8000`,
      // A full run across three viewports issues many hundreds of API calls from
      // one address, which exceeds the production request budget. Raising it here
      // keeps the guard enabled (it still protects a real deployment) without
      // failing tests on unrelated rate-limit responses.
      env: { SPACEAGRISIM_GENERAL_RATE_LIMIT_PER_MINUTE: "5000" },
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60000,
    },
    {
      // Run against the production build rather than the dev server: it removes Vite's
      // on-demand transforms and HMR churn from the timing of every assertion, and it is the
      // bundle a user actually receives. `preview` carries the same `/api` proxy as `dev`.
      // The manifest is not in the tree (see scripts/npm.mjs), so this calls the binaries the
      // prepared node_modules exposes instead of running through `npm run`.
      command: "node node_modules/vite/bin/vite.js build"
        + " && node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 60000,
    },
  ],
});
