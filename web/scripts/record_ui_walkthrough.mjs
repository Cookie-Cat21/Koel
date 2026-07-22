/**
 * Record Browse filters + Layer A/B charts for artifact review.
 * Requires dash on BASE (default http://127.0.0.1:3000) with demo auth.
 */
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const BASE = process.env.BASE_URL || "http://127.0.0.1:3000";
const OUT_DIR = process.env.ARTIFACT_DIR || "/opt/cursor/artifacts";
const STILL_DIR = path.join(OUT_DIR, "ui-stills");
const WEB_M = path.join(OUT_DIR, "koel-ui-walkthrough.webm");
const MP4 = path.join(OUT_DIR, "koel-ui-walkthrough.mp4");
const PASS_DIR = path.resolve("..", "docs/factory/passes");

fs.mkdirSync(STILL_DIR, { recursive: true });
for (const f of fs.readdirSync(STILL_DIR)) {
  if (f.endsWith(".png")) fs.unlinkSync(path.join(STILL_DIR, f));
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: OUT_DIR, size: { width: 1440, height: 900 } },
});
const page = await context.newPage();
let n = 0;
async function still(name) {
  n += 1;
  const p = path.join(STILL_DIR, `${String(n).padStart(2, "0")}-${name}.png`);
  await page.screenshot({ path: p, fullPage: false });
  console.log("still", p);
}

try {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 90000 });
  await page.fill('input[name="telegram_id"]', "9001001");
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 30000,
  });
  await page.waitForTimeout(900);
  await still("overview");

  await page.goto(`${BASE}/market`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await still("browse-all");

  await page.selectOption("#market_sector", { label: "Banks" });
  await Promise.all([
    page.waitForURL(/sector=/),
    page.getByRole("button", { name: /^Apply$/i }).click(),
  ]);
  await page.waitForTimeout(1000);
  await still("browse-banks");

  // Prefer symbol row link in the table
  const symbolLink = page.locator('a[href*="/symbols/"]').first();
  await symbolLink.click();
  await page.waitForURL(/\/symbols\//);
  await page.waitForTimeout(1800);
  await still("symbol-hero");

  await page.locator('[data-testid="expand-chart"]').first().click();
  await page.waitForSelector('[data-testid="expand-chart-dialog"]', {
    timeout: 15000,
  });
  await page.waitForTimeout(2500);
  await still("expand-koel");

  await page
    .locator('[data-testid="expand-chart-dialog"]')
    .getByRole("button", { name: /^TradingView$/i })
    .click();
  await page.waitForTimeout(3500);
  await still("expand-tv");

  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);

  await page.goto(`${BASE}/market?sector=Telecommunications`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(900);
  await still("browse-telecom");

  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  await still("overview-end");
} catch (err) {
  console.error("record failed", err);
  await still("error");
  throw err;
} finally {
  const vid = page.video();
  await page.close();
  await context.close();
  await browser.close();
  if (vid) {
    const raw = await vid.path();
    fs.renameSync(raw, WEB_M);
    console.log("webm", WEB_M);
  }
}

const ff = spawnSync(
  "ffmpeg",
  [
    "-y",
    "-i",
    WEB_M,
    "-c:v",
    "libx264",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    MP4,
  ],
  { encoding: "utf8" },
);
if (ff.status !== 0) {
  console.error(ff.stderr);
  process.exit(1);
}
console.log("mp4", MP4, fs.statSync(MP4).size);

// Mirror key stills into docs/factory/passes for the PR
fs.mkdirSync(PASS_DIR, { recursive: true });
const map = [
  ["02-browse-all.png", "01-browse.png"],
  ["03-browse-banks.png", "02-sector-filter.png"],
  ["04-symbol-hero.png", "03-chart.png"],
  ["05-expand-koel.png", "04-layers.png"],
  ["06-expand-tv.png", "05-tradingview.png"],
];
for (const [src, dest] of map) {
  const from = path.join(STILL_DIR, src);
  if (fs.existsSync(from)) {
    fs.copyFileSync(from, path.join(PASS_DIR, dest));
    console.log("copied", dest);
  }
}
