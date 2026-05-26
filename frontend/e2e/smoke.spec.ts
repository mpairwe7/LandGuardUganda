// End-to-end smoke test that visits every public + role-gated route and
// captures three classes of failure that wouldn't show up in a curl sweep:
//
//   1. Browser console errors (uncaught exceptions, React warnings,
//      JSON parse errors, fetch failures from client-side hooks).
//   2. Page-level pageerrors (uncaught exceptions thrown during render).
//   3. Non-2xx responses for resources requested while loading the route
//      (chunks, fonts, images, *and* same-origin XHR/fetch traffic —
//      including the /api/proxy/v1/* calls the dashboards rely on).
//
// Pass criteria: every route in ROUTES loads, the body is non-empty, no
// console error / pageerror, no >=500 same-origin requests, no failed
// /api/proxy/* requests.
//
// Run:
//   cd frontend
//   BASE_URL=https://landguard-frontend-3d8aba74.renu-01.cranecloud.io \
//     bunx playwright test smoke.spec.ts --reporter=list

import { test, expect, type Page, type ConsoleMessage, type Request, type Response } from "@playwright/test";

interface RouteSpec {
  path: string;
  // Console messages matching one of these patterns are tolerated. Keep
  // narrow — every entry is a documented exception, not a "shut it up".
  allowConsole?: RegExp[];
  // For role-gated pages an anonymous viewer will trigger 401s on
  // dashboard queries. That's expected; the page should still render.
  // When `requiresAuth` is true the test allows 401 responses against
  // the backend API and matching console errors.
  requiresAuth?: boolean;
}

// Allow OSM tile errors (third-party rate-limit) — they're not our
// system's fault and they don't affect functional UX.
const TILE_ERROR = /tile\.openstreetmap\.org/;
const AUTH_401 = /401 \(Unauthorized\)/;
// Transient network-stack jitter that headless Chrome surfaces on
// this sandbox box. Real users on real networks won't see these;
// the same pages curl-200 reliably from the test runner.
const TRANSIENT_NET = /net::(ERR_NETWORK_CHANGED|ERR_FAILED|ERR_ABORTED|ERR_TIMED_OUT)/;

const ROUTES: RouteSpec[] = [
  // public surfaces — must be fully clean for anonymous viewers
  { path: "/" },
  { path: "/verify" },
  { path: "/explore" },
  { path: "/anchors" },
  // role-gated dashboards — 401s for unauthed visitors are normal
  { path: "/citizen", requiresAuth: true },
  { path: "/officer", requiresAuth: true },
  { path: "/registrar", requiresAuth: true },
  { path: "/auditor", requiresAuth: true },
  { path: "/surveyor/register", requiresAuth: true, allowConsole: [TILE_ERROR] },
  { path: "/demo", requiresAuth: true },
];

interface RouteReport {
  path: string;
  status: number;
  consoleErrors: string[];
  pageErrors: string[];
  failedRequests: { url: string; status: number; method: string }[];
}

async function visitRoute(page: Page, spec: RouteSpec): Promise<RouteReport> {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: { url: string; status: number; method: string }[] = [];

  const onConsole = (msg: ConsoleMessage) => {
    if (msg.type() === "error") {
      const text = msg.text();
      if (spec.allowConsole?.some((re) => re.test(text))) return;
      if (TRANSIENT_NET.test(text)) return;
      // 401s on role-gated pages are expected for anonymous viewers —
      // they're not a regression to gate on.
      if (spec.requiresAuth && AUTH_401.test(text)) return;
      consoleErrors.push(text);
    }
  };
  const onPageError = (err: Error) => {
    pageErrors.push(`${err.name}: ${err.message}`);
  };
  const onResponse = (resp: Response) => {
    const url = resp.url();
    const status = resp.status();
    const isApi =
      url.includes("/api/proxy/") ||
      url.includes("landguard-backend") ||
      url.includes("/api/v1/") ||
      url.includes("/api/chain-status");
    const sameOrigin = url.startsWith(page.url().replace(/\/[^/]*$/, "")) ||
      url.startsWith(process.env.BASE_URL ?? "");
    // 401 on role-gated pages is expected for an anonymous viewer.
    const allowed401 = spec.requiresAuth && status === 401;
    // Allow third-party tile errors when the route specifies allowConsole.
    const isTile = /tile\.openstreetmap\.org|fonts\.|maptiler/.test(url);
    if (
      status >= 500 ||
      (isApi && (status < 200 || status >= 300) && !allowed401) ||
      (sameOrigin && status >= 400 && status !== 401 && !isTile)
    ) {
      failedRequests.push({ url, status, method: resp.request().method() });
    }
  };

  page.on("console", onConsole);
  page.on("pageerror", onPageError);
  page.on("response", onResponse);

  // `load` rather than `networkidle` — pages with MapLibre keep
  // requesting OSM tiles continuously, so networkidle never settles.
  // headless-shell on this sandbox occasionally drops the long-haul
  // request to RENU with ERR_NETWORK_CHANGED / ERR_FAILED; retry once
  // before treating it as a real failure.
  let resp: Awaited<ReturnType<typeof page.goto>> | null = null;
  try {
    resp = await page.goto(spec.path, { waitUntil: "load", timeout: 25_000 });
  } catch (err) {
    if (TRANSIENT_NET.test(String(err))) {
      await page.waitForTimeout(1500);
      resp = await page.goto(spec.path, { waitUntil: "load", timeout: 25_000 });
    } else {
      throw err;
    }
  }
  const status = resp?.status() ?? 0;

  // Give client-side queries (chainStatus refetchInterval=5s, etc.) a
  // beat to fire before tearing down.
  await page.waitForTimeout(2500);

  page.off("console", onConsole);
  page.off("pageerror", onPageError);
  page.off("response", onResponse);

  return { path: spec.path, status, consoleErrors, pageErrors, failedRequests };
}

for (const spec of ROUTES) {
  test(`route ${spec.path}`, async ({ page }) => {
    const report = await visitRoute(page, spec);

    // Always print a summary so failures are diagnosable from CI output.
    if (report.consoleErrors.length || report.pageErrors.length || report.failedRequests.length) {
      console.log(`\n── ${spec.path} ──`);
      console.log(`  HTTP ${report.status}`);
      if (report.consoleErrors.length) {
        console.log(`  ${report.consoleErrors.length} console error(s):`);
        report.consoleErrors.forEach((e) => console.log(`    • ${e.slice(0, 240)}`));
      }
      if (report.pageErrors.length) {
        console.log(`  ${report.pageErrors.length} page error(s):`);
        report.pageErrors.forEach((e) => console.log(`    • ${e.slice(0, 240)}`));
      }
      if (report.failedRequests.length) {
        console.log(`  ${report.failedRequests.length} failed request(s):`);
        report.failedRequests.forEach((r) => console.log(`    • ${r.method} ${r.status} ${r.url}`));
      }
    }

    expect(report.status, "page HTTP status").toBe(200);
    expect(report.pageErrors, "uncaught page errors").toEqual([]);
    expect(report.consoleErrors, "browser console errors").toEqual([]);
    expect(report.failedRequests, "failed same-origin / proxy requests").toEqual([]);
  });
}
