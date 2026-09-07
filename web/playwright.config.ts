import { defineConfig, devices } from "@playwright/test";

const port = process.env.PLAYWRIGHT_PORT ?? "3000";
const frontendCommand = process.env.PLAYWRIGHT_FRONTEND_COMMAND ?? `pnpm dev --port ${port}`;

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
      url: "http://127.0.0.1:8765/health",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: frontendCommand,
      url: `http://localhost:${port}`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
