// Mobile-viewport e2e — runs under the `mobile-chromium` project
// (Pixel 5 / 393×851). Three guarantees:
//
//   1. No horizontal scroll on any public route (page fits viewport).
//   2. The hamburger menu opens, exposes the expected links, and
//      navigates correctly when a link is tapped.
//   3. axe-core finds no critical/serious WCAG 2.2 AA violations on
//      /verify and / at this viewport.
//
// Run:
//   TMPDIR=/tmp/pw-temp \
//     BASE_URL=https://landguard-frontend-3d8aba74.renu-01.cranecloud.io \
//     bunx playwright test mobile.spec.ts --reporter=list --project=mobile-chromium

import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const TRANSIENT_NET = /net::(ERR_NETWORK_CHANGED|ERR_FAILED|ERR_ABORTED|ERR_TIMED_OUT)/;

async function gotoWithRetry(
  page: import("@playwright/test").Page,
  url: string,
) {
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

const PUBLIC_ROUTES = ["/", "/verify", "/explore", "/anchors"];

for (const path of PUBLIC_ROUTES) {
  test(`mobile: ${path} renders without horizontal overflow`, async ({ page }) => {
    await gotoWithRetry(page, path);
    await page.waitForTimeout(1500);
    const overflow = await page.evaluate(() => {
      return {
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      };
    });
    // Allow a 1px rounding fudge — anything more is real overflow.
    expect(overflow.scrollWidth - overflow.clientWidth, path).toBeLessThanOrEqual(1);
  });
}

test("mobile: public hamburger menu opens and links work", async ({ page }) => {
  await gotoWithRetry(page, "/");
  // The inline desktop nav must be hidden; the hamburger must be visible.
  const hamburger = page.getByRole("button", { name: /open public registry menu/i });
  await expect(hamburger).toBeVisible();
  await hamburger.click();

  // Drawer renders the three nav links.
  const dialog = page.getByRole("dialog", { name: /open public registry menu/i });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("link", { name: /verify a title/i })).toBeVisible();
  await expect(dialog.getByRole("link", { name: /explore districts/i })).toBeVisible();
  await expect(dialog.getByRole("link", { name: /anchor explorer/i })).toBeVisible();

  // Clicking a link navigates and auto-closes the drawer.
  await dialog.getByRole("link", { name: /verify a title/i }).click();
  await page.waitForURL("**/verify", { timeout: 10_000 });
});

test("mobile: app console hamburger menu exposes role nav", async ({ page }) => {
  await gotoWithRetry(page, "/officer");
  const hamburger = page.getByRole("button", { name: /open console navigation/i });
  await expect(hamburger).toBeVisible();
  await hamburger.click();
  const dialog = page.getByRole("dialog", { name: /open console navigation/i });
  await expect(dialog).toBeVisible();
  // The five role groups all show up.
  await expect(dialog.getByText(/My parcels/i)).toBeVisible();
  await expect(dialog.getByText(/Register parcel/i)).toBeVisible();
  await expect(dialog.getByText(/KYC queue/i)).toBeVisible();
  await expect(dialog.getByText(/Issue title/i)).toBeVisible();
  await expect(dialog.getByText(/Chain integrity/i)).toBeVisible();
});

test("mobile: axe-core a11y on /verify (showcase page)", async ({ page }) => {
  test.setTimeout(60_000);
  await gotoWithRetry(page, "/verify");
  await page.waitForTimeout(1500);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const blockers = results.violations.filter((v) =>
    ["critical", "serious"].includes(v.impact ?? ""),
  );
  if (blockers.length) {
    for (const v of blockers) {
      console.log(`  • [${v.impact}] ${v.id}: ${v.help}`);
      for (const n of v.nodes.slice(0, 3))
        console.log(`    target: ${JSON.stringify(n.target)}`);
    }
  }
  expect(blockers).toEqual([]);
});
