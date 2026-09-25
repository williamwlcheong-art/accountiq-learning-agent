import { defineConfig, devices } from "@playwright/test";

const port = process.env.PLAYWRIGHT_PORT ?? "3000";
const frontendCommand = process.env.PLAYWRIGHT_FRONTEND_COMMAND ?? `pnpm dev --port ${port}`;
// The backend port is overridable so the suite can run on a machine where 8765 is taken.
const backendPort = process.env.PLAYWRIGHT_BACKEND_PORT ?? "8765";

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: `http://localhost:${port}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 5"] }, testMatch: /responsive\.spec\.ts/ },
  ],
  webServer: [
    {
      command: "../scripts/start-e2e-backend.sh",
      env: { PORT: backendPort },
      url: `http://127.0.0.1:${backendPort}/health`,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: frontendCommand,
      // Point the Next proxy at the backend this run started, not the default port.
      env: { FASTAPI_ORIGIN: `http://127.0.0.1:${backendPort}` },
      url: `http://localhost:${port}`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
