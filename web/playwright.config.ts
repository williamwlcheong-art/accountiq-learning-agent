import { defineConfig, devices } from "@playwright/test";

const frontendCommand = process.env.PLAYWRIGHT_FRONTEND_COMMAND ?? "npm run dev";
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
const frontendURL = process.env.PLAYWRIGHT_FRONTEND_URL ?? baseURL;

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL,
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
      timeout: 60_000,
    },
    {
      command: frontendCommand,
      url: frontendURL,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
