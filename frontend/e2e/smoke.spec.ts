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
}

const ROUTES: RouteSpec[] = [
  // public surfaces
  { path: "/" },
  { path: "/verify" },
  { path: "/explore" },
  { path: "/anchors" },
  // role-gated dashboards — render even without auth (data may be empty)
  { path: "/citizen" },
  { path: "/officer" },
  { path: "/registrar" },
  { path: "/auditor" },
  { path: "/surveyor/register" },
  { path: "/demo" },
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
      consoleErrors.push(text);
    }
  };
  const onPageError = (err: Error) => {
    pageErrors.push(`${err.name}: ${err.message}`);
  };
  const onResponse = (resp: Response) => {
    const url = resp.url();
    const status = resp.status();
    // Treat any >=500 OR /api/proxy/* non-2xx as a real failure.
    const isApi = url.includes("/api/proxy/");
    if (status >= 500 || (isApi && (status < 200 || status >= 300))) {
      failedRequests.push({ url, status, method: resp.request().method() });
    }
  };

  page.on("console", onConsole);
  page.on("pageerror", onPageError);
  page.on("response", onResponse);

  const resp = await page.goto(spec.path, { waitUntil: "networkidle", timeout: 30_000 });
  const status = resp?.status() ?? 0;

  // Give client-side queries (chainStatus refetchInterval=5s, etc.) a
  // beat to fire before tearing down.
  await page.waitForTimeout(1500);

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
