/**
 * Playwright smoke test — verifies the map app loads without console errors.
 * Run:  npx playwright test tests/test_html_map.mjs
 *   or: node tests/test_html_map.mjs            (standalone)
 */
import { chromium } from "playwright";

const BASE_URL = process.env.BASE_URL || "http://localhost:8080";
const TIMEOUT = 30_000;

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const errors = [];
  const warnings = [];
  const failedRequests = [];

  // Collect console errors
  page.on("console", msg => {
    if (msg.type() === "error") errors.push(msg.text());
    if (msg.type() === "warning") warnings.push(msg.text());
  });

  // Collect failed network requests (4xx / 5xx), ignoring expected missing assets
  page.on("response", resp => {
    if (resp.status() >= 400 && !resp.url().includes("logo.png")) {
      failedRequests.push(`${resp.status()} ${resp.url()}`);
    }
  });

  console.log(`⏳ Loading ${BASE_URL} …`);
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded", timeout: TIMEOUT });

  // Wait for map canvas to appear
  await page.waitForSelector("canvas", { timeout: TIMEOUT });
  console.log("✅ Map canvas rendered");

  // Give time for tiles + fonts + Overpass road fetch to load
  await page.waitForTimeout(15000);

  // Animation check: ensure at least one road label has been animated
  const animationTriggered = await page.evaluate(() => {
    return document.querySelectorAll(".road-callout[data-animated='true']").length > 0;
  });

  // Check for "Roads loaded" log (Overpass fetch succeeded)
  const roadsLoaded = await page.evaluate(() => {
    return window.__roadsLoaded || false;
  });

  // --- Report ---
  console.log("\n═══ Results ═══");

  if (failedRequests.length) {
    console.log(`\n❌ Failed requests (${failedRequests.length}):`);
    failedRequests.forEach(r => console.log(`   ${r}`));
  } else {
    console.log("✅ No failed HTTP requests");
  }

  // Filter out non-critical errors (tile 404s, missing optional assets, generic resource errors)
  const criticalErrors = errors.filter(e =>
    !e.includes("arcgisonline") &&
    !e.includes("basemaps.cartocdn") &&
    !e.includes("logo.png") &&
    !e.includes("Failed to load resource")
  );

  if (criticalErrors.length) {
    console.log(`\n❌ Console errors (${criticalErrors.length}):`);
    criticalErrors.forEach(e => console.log(`   ${e}`));
  } else {
    console.log("✅ No critical console errors");
  }

  if (warnings.length) {
    console.log(`\n⚠️  Warnings (${warnings.length}):`);
    warnings.forEach(w => console.log(`   ${w}`));
  }

  if (animationTriggered) {
    console.log("✅ Road label appear animation triggered");
  } else {
    console.log("⚠️  Road label appear animation NOT detected");
  }

  // Font-specific check
  const fontErrors = failedRequests.filter(r => r.includes("/font/") || r.includes(".pbf"));
  if (fontErrors.length) {
    console.log(`\n❌ FONT LOADING FAILURES:`);
    fontErrors.forEach(e => console.log(`   ${e}`));
  } else {
    console.log("✅ All font/glyph requests succeeded");
  }

  await browser.close();

  // Exit with error if critical issues found
  const hasCritical = criticalErrors.length > 0 || fontErrors.length > 0;
  process.exit(hasCritical ? 1 : 0);
})();
