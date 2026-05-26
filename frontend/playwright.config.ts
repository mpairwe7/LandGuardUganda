import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

/**
 * Playwright config — drives the e2e/ specs.
 *
 * On the shared dev box, full Chromium crashes with SIGTRAP. We
 * auto-discover a `chrome-headless-shell` binary from the playwright
 * browser cache and use that with sandbox flags relaxed. CI machines
 * (which can run full chromium) bypass this when PW_USE_HEADLESS_SHELL
 * isn't set or the binary path doesn't exist.
 *
 * Reproduce:
 *   cd frontend
 *   bun install --frozen-lockfile
 *   bunx playwright install chromium chromium-headless-shell
 *   BASE_URL=http://localhost:3031 bun run e2e
 */
const HEADLESS_SHELL_CANDIDATES = [
  "/home/developer/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell",
  "/home/developer/.cache/ms-playwright/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell",
];
const headlessShell = HEADLESS_SHELL_CANDIDATES.find((p) => existsSync(p));
const useShell = process.env.PW_USE_HEADLESS_SHELL !== "0" && headlessShell;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3031",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: useShell
          ? {
              executablePath: headlessShell,
              args: [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                // GPU sub-process SIGTRAPs on this sandbox box — force
                // it in-process and use software rendering (swiftshader)
                // so headless rendering still works.
                "--in-process-gpu",
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
                "--disable-features=VizDisplayCompositor",
              ],
            }
          : undefined,
      },
    },
    {
      // Mobile project for mobile.spec.ts only. iPhone 15-ish viewport
      // (390×844) reproduces the phone-class layout reliably. Uses the
      // same headless-shell launcher so the GPU stays in-process and
      // doesn't trip SIGTRAP on the sandbox runner.
      name: "mobile-chromium",
      testMatch: /mobile\.spec\.ts/,
      use: {
        ...devices["Pixel 5"],
        launchOptions: useShell
          ? {
              executablePath: headlessShell,
              args: [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--in-process-gpu",
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
                "--disable-features=VizDisplayCompositor",
              ],
            }
          : undefined,
      },
    },
  ],
});
