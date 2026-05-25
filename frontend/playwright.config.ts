import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config — drives the e2e/ specs.
 *
 * For the showcase the only spec that runs is `accessibility.spec.ts`,
 * which formally binds the WCAG 2.2 AA promise via @axe-core/playwright.
 *
 * Reproduce:
 *   cd frontend
 *   bun install --frozen-lockfile
 *   bunx playwright install --with-deps chromium
 *   # In another terminal, start the production frontend:
 *   #   bun run build && PORT=3031 bun run start --port 3031
 *   BASE_URL=http://localhost:3031 bun run e2e
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3031",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
