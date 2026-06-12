import { defineConfig, devices } from "@playwright/test";

/**
 * E2E suite for Job-Applyr.
 *
 * All backend APIs are mocked via route interception (see e2e/helpers/mock.ts)
 * so no real credentials, SMTP, LLM, CV parsing, or live job portals are ever
 * touched. The web server below only serves the frontend.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  workers: 4,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  reporter: [["line"], ["html", { open: "never" }]],
  outputDir: "./e2e-results",
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    permissions: ["clipboard-read", "clipboard-write"],
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run dev -- --port 5174 --strictPort --host 127.0.0.1",
    url: "http://127.0.0.1:5174",
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
