import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 12000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
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
      command: "npm run dev -- --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 60000,
    },
  ],
});
