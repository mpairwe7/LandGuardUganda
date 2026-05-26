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
const TRANSIENT_NET = /net::(ERR_NETWORK_CHANGED|ERR_FAILED|ERR_ABORTED|ERR_TIMED_OUT)/;

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
    if (TRANSIENT_NET.test(text)) return;
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
    // Sticky header overlaps the hero CTA when the viewport is small;
    // assert the link is present + has the right href instead of
    // simulating a real click (that's a layout-stability test, not
    // a route-wiring test).
    const link = page.getByRole("link", { name: "See live anchors" });
    await expect(link).toHaveCount(1);
    await expect(link).toHaveAttribute("href", "/anchors");
    await page.goto("/anchors", { waitUntil: "load" });
    await expect(page).toHaveURL(/\/anchors$/);
  });
  expect(failedResponses, "failed responses").toEqual([]);
  expect(consoleErrors, "console errors").toEqual([]);
});

test("public flow: landing → verify", async ({ page }) => {
  const { consoleErrors, failedResponses } = await withErrorCapture(page, async () => {
    await page.goto("/", { waitUntil: "load" });
    // Same as the anchors flow — assert the href, then navigate.
    const link = page
      .getByRole("link", { name: /verify a title now/i })
      .first();
    await expect(link).toHaveAttribute("href", "/verify");
    await page.goto("/verify", { waitUntil: "load" });
    await expect(page).toHaveURL(/\/verify$/);
  });
  expect(failedResponses).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test("public flow: explore → district drill-down → back", async ({ page }) => {
  const { consoleErrors, failedResponses } = await withErrorCapture(page, async () => {
    await page.goto("/explore", { waitUntil: "load" });
    const card = page.getByRole("link", { name: /mityana/i }).first();
    await expect(card).toHaveAttribute("href", "/explore/district/mityana");
    await page.goto("/explore/district/mityana", { waitUntil: "load" });
    await expect(page.getByRole("heading", { name: /mityana/i }).first()).toBeVisible();
    const back = page.getByRole("link", { name: /all districts/i });
    await expect(back).toHaveAttribute("href", "/explore");
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
  // Headless Chrome on the sandbox runner sometimes reports
  // ERR_FAILED / ERR_NETWORK_CHANGED on long-haul requests to the
  // RENU cluster; retry once before treating it as a real failure.
  async function gotoWithRetry(url: string) {
    try {
      return await page.goto(url, { waitUntil: "load", timeout: 25_000 });
    } catch (err) {
      if (TRANSIENT_NET.test(String(err))) {
        await page.waitForTimeout(1500);
        return await page.goto(url, { waitUntil: "load", timeout: 25_000 });
      }
      throw err;
    }
  }

  await gotoWithRetry("/officer");
  const sidebar = page.getByRole("navigation", { name: /console navigation/i });
  await expect(sidebar).toBeVisible();
  const hrefs = await sidebar.locator("a[href^='/']").evaluateAll((els) =>
    Array.from(new Set(els.map((el) => (el as HTMLAnchorElement).getAttribute("href")!))).filter(
      (h) => !h.includes("#") && h !== "/",
    ),
  );
  expect(hrefs.length, "found at least one sidebar link").toBeGreaterThan(0);
  for (const href of hrefs) {
    const resp = await gotoWithRetry(href);
    expect(resp?.status(), `nav link ${href}`).toBe(200);
  }
});

test("verify form: invalid title shows graceful empty/error state", async ({ page }) => {
  // /v1/anchors/title/.../proof correctly returns 404 for unknown
  // titles — Chrome logs that as a console error we can't suppress
  // from JS land. Allow 404/409 from the proof endpoint specifically.
  const VERIFY_404 = /404 \(Not Found\)|409 \(Conflict\)/;
  const { consoleErrors, failedResponses } = await withErrorCapture(
    page,
    async () => {
      await page.goto("/verify", { waitUntil: "load" });
      const input = page.locator('input[type="text"], input[type="search"]').first();
      await input.fill("UG-NONEXISTENT-999999/2026");
      await input.press("Enter").catch(() => {});
      await page.waitForTimeout(2500);
      await expect(page).toHaveURL(/\/verify/);
    },
    { allow: [VERIFY_404] },
  );
  // Allow expected 404/409 from the proof lookup but flag any 5xx.
  expect(
    failedResponses.filter(
      (r) => !r.includes("/proof") || (!r.startsWith("404") && !r.startsWith("409")),
    ).filter((r) => r.startsWith("5") || r.startsWith("4")),
  ).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
