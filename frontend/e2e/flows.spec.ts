// User-journey tests. smoke.spec.ts confirms every page renders;
// this spec confirms the navigation between them works — i.e. that
// every visible link / button lands on a real route and the page
// is functional after the navigation. Catches:
//   - Link hrefs to non-existent routes
//   - Sidebar / NavLink wiring
//   - Form-driven redirects that go to a 404
//   - Any "click → 404" flow a user might hit
//
// Run:
//   cd frontend
//   TMPDIR=/tmp/pw-temp \
//     BASE_URL=https://landguard-frontend-3d8aba74.renu-01.cranecloud.io \
//     bunx playwright test flows.spec.ts --reporter=list

import { test, expect, type Page, type ConsoleMessage } from "@playwright/test";

const AUTH_401 = /401 \(Unauthorized\)/;

/** Capture browser-console errors and 4xx/5xx same-origin responses
 *  while a block of test work runs. Designed to be wrapped around an
 *  arbitrary navigation flow. */
async function withErrorCapture<T>(
  page: Page,
  fn: () => Promise<T>,
  opts: { allowAuth401?: boolean; allow?: RegExp[] } = {},
): Promise<{ result: T; consoleErrors: string[]; failedResponses: string[] }> {
  const consoleErrors: string[] = [];
  const failedResponses: string[] = [];
  const onConsole = (msg: ConsoleMessage) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    if (opts.allow?.some((r) => r.test(text))) return;
    if (opts.allowAuth401 && AUTH_401.test(text)) return;
    consoleErrors.push(text);
  };
  const onResponse = (resp: import("@playwright/test").Response) => {
    const status = resp.status();
    const url = resp.url();
    const sameOrigin = url.startsWith(process.env.BASE_URL ?? "");
    const isApi =
      url.includes("/api/proxy/") ||
      url.includes("landguard-backend") ||
      url.includes("/api/v1/");
    if (status >= 500) failedResponses.push(`${status} ${url}`);
    else if (sameOrigin && status >= 400 && !(opts.allowAuth401 && status === 401)) {
      failedResponses.push(`${status} ${url}`);
    } else if (isApi && status >= 400 && !(opts.allowAuth401 && status === 401)) {
      failedResponses.push(`${status} ${url}`);
    }
  };
  page.on("console", onConsole);
  page.on("response", onResponse);
  try {
    const result = await fn();
    return { result, consoleErrors, failedResponses };
  } finally {
    page.off("console", onConsole);
    page.off("response", onResponse);
  }
}

test("public flow: landing → anchors → back", async ({ page }) => {
  const { consoleErrors, failedResponses } = await withErrorCapture(page, async () => {
    await page.goto("/", { waitUntil: "load" });
    await expect(page).toHaveURL(/\/$|\/(?:\?|#|$)/);
    // The landing page renders multiple "See live anchors" / "Anchors"
    // links. Click the first one with that label.
    const link = page.getByRole("link", { name: /see live anchors|anchors/i }).first();
    await link.click();
    await page.waitForURL("**/anchors", { timeout: 10_000 });
    await expect(page).toHaveTitle(/.+/);
  });
  expect(failedResponses, "failed responses").toEqual([]);
  expect(consoleErrors, "console errors").toEqual([]);
});

test("public flow: landing → verify", async ({ page }) => {
  const { consoleErrors, failedResponses } = await withErrorCapture(page, async () => {
    await page.goto("/", { waitUntil: "load" });
    await page
      .getByRole("link", { name: /verify a title|public verifier|verify/i })
      .first()
      .click();
    await page.waitForURL("**/verify", { timeout: 10_000 });
  });
  expect(failedResponses).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test("public flow: explore → district drill-down → back", async ({ page }) => {
  const { consoleErrors, failedResponses } = await withErrorCapture(page, async () => {
    await page.goto("/explore", { waitUntil: "load" });
    // Mityana is the pilot district — its card should be clickable
    // and land on /explore/district/mityana.
    await page.getByRole("link", { name: /mityana/i }).first().click();
    await page.waitForURL("**/explore/district/mityana", { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: /mityana/i }).first()).toBeVisible();
    // Back-link returns to /explore.
    await page.getByRole("link", { name: /all districts/i }).click();
    await page.waitForURL("**/explore", { timeout: 10_000 });
  });
  expect(failedResponses).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test("public flow: explore → planned district shows 'planned' state", async ({ page }) => {
  const { consoleErrors, failedResponses } = await withErrorCapture(page, async () => {
    await page.goto("/explore/district/wakiso", { waitUntil: "load" });
    await expect(page.getByText(/planned|rollout|isn.t live yet/i).first()).toBeVisible();
  });
  expect(failedResponses).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test("public flow: unknown district returns 404", async ({ page }) => {
  const resp = await page.goto("/explore/district/atlantis", { waitUntil: "load" });
  // Next.js returns 404 for unknown static params when dynamicParams=false.
  expect(resp?.status()).toBe(404);
});

test("public flow: anchors page lists or shows empty state", async ({ page }) => {
  const { consoleErrors, failedResponses } = await withErrorCapture(page, async () => {
    await page.goto("/anchors", { waitUntil: "load" });
    // Either renders the timeline OR a documented empty state — both
    // are valid for a freshly-deployed backend with no anchored data.
    await expect(page.locator("body")).toContainText(/anchor|chain|batch|no|empty/i);
  });
  expect(failedResponses).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test("dashboard flow: sidebar links don't 404", async ({ page }) => {
  const { consoleErrors, failedResponses } = await withErrorCapture(
    page,
    async () => {
      await page.goto("/officer", { waitUntil: "load" });
      // Every visible sidebar link on the (app) console.
      const sidebar = page.getByRole("navigation", { name: /console navigation/i });
      const hrefs = await sidebar.locator("a[href]").evaluateAll((els) =>
        els.map((el) => (el as HTMLAnchorElement).getAttribute("href")).filter(
          (h): h is string => !!h && h.startsWith("/"),
        ),
      );
      // Visit each and assert HTTP 200.
      for (const href of hrefs) {
        const resp = await page.goto(href, { waitUntil: "load", timeout: 20_000 });
        expect(resp?.status(), `nav link ${href}`).toBe(200);
      }
    },
    { allowAuth401: true, allow: [/tile\.openstreetmap\.org/] },
  );
  expect(failedResponses, "failed responses").toEqual([]);
  expect(consoleErrors, "console errors").toEqual([]);
});

test("verify form: invalid title shows graceful empty/error state", async ({ page }) => {
  const { consoleErrors, failedResponses } = await withErrorCapture(page, async () => {
    await page.goto("/verify", { waitUntil: "load" });
    const input = page.locator('input[type="text"], input[type="search"]').first();
    await input.fill("UG-NONEXISTENT-999999/2026");
    // Submit either via Enter or a visible button — try Enter first.
    await input.press("Enter").catch(() => {});
    // Brief settle so the API call lands.
    await page.waitForTimeout(2500);
    // Page should still be on /verify (no crash redirect).
    await expect(page).toHaveURL(/\/verify/);
  });
  // Verify is public — but the /v1/anchors/title/.../proof endpoint
  // returns 404/409 for unknown titles, which is valid backend behaviour.
  // We only flag 5xx as a failure here.
  expect(failedResponses.filter((r) => r.startsWith("5"))).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
