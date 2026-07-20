/**
 * Unit harness for period-returns + tech-labels helpers.
 * Invoked via npx tsx from tests/test_web_route_regressions.py
 */
import assert from "node:assert/strict";

import {
  adjustBarsForSplits,
  adjustFactor,
} from "./src/lib/api/corporate-actions.ts";
import {
  closesFromBars,
  computePeriodReturns,
  returnPctAtCalendarDays,
  returnPctAtHorizon,
} from "./src/lib/api/period-returns.ts";
import {
  barsFromDaily,
  computeTechLabels,
} from "./src/lib/api/tech-labels.ts";
import {
  computeFundamentals,
  scaleEquityUnits,
} from "./src/lib/api/fundamentals.ts";

function testPeriodReturns() {
  assert.equal(returnPctAtHorizon([], 5), null);
  assert.equal(returnPctAtHorizon([100], 5), null);
  const closes = Array.from({ length: 10 }, (_, i) => 100 + i);
  // length 10, sessions 5 → prior at index 4 (100+4=104), latest 109
  const pct = returnPctAtHorizon(closes, 5);
  assert.ok(pct != null);
  assert.ok(Math.abs(pct! - ((109 - 104) / 104) * 100) < 1e-9);

  const long = Array.from({ length: 230 }, (_, i) => 50 + i * 0.1);
  const rets = computePeriodReturns(long);
  assert.ok(rets["1W"] != null);
  assert.ok(rets["1M"] != null);
  assert.ok(rets["3M"] != null);
  // CSE-depth fallback (~220 sessions) — NYSE 252 would stay null.
  assert.ok(rets["1Y"] != null);

  // Calendar 1Y: 242 sessions evenly spanning 364 calendar days (CSE period=5).
  const dated: { trade_date: string; close: number }[] = [];
  const startMs = Date.UTC(2025, 6, 17); // 2025-07-17
  const spanDays = 364;
  for (let i = 0; i < 242; i++) {
    const dayOffset = Math.round((i * spanDays) / 241);
    const d = new Date(startMs + dayOffset * 86_400_000);
    dated.push({
      trade_date: d.toISOString().slice(0, 10),
      close: 100 + i * 0.05,
    });
  }
  const cal = returnPctAtCalendarDays(dated, 365);
  assert.ok(cal != null, "calendar 1Y over CSE-depth series");
  const withDates = computePeriodReturns(
    dated.map((b) => b.close),
    dated,
  );
  assert.ok(withDates["1Y"] != null);

  assert.deepEqual(
    closesFromBars([{ close: 1 }, { price: 2 }, { close: "x" }, { close: -1 }]),
    [1, 2],
  );
}

function testTechLabels() {
  const bars = barsFromDaily(
    Array.from({ length: 80 }, (_, i) => ({
      high: 110 + i * 0.2,
      low: 90 + i * 0.2,
      close: 100 + i * 0.2,
    })),
  );
  assert.equal(bars.length, 80);
  const labels = computeTechLabels(bars);
  assert.ok(labels.sma50_pct != null);
  assert.ok(labels.atr_pct != null);
  assert.ok(labels.macd_bias === "BULL" || labels.macd_bias === "BEAR");
  assert.ok(labels.bb_pos != null);
  assert.ok(labels.week52_pct != null);
}

function testFundamentalsHonesty() {
  assert.equal(scaleEquityUnits(5, "millions"), 5_000_000);
  // Tiny units stay rejected; unknown mid-range promotes to Rs mn.
  assert.equal(scaleEquityUnits(1, "units"), null);
  assert.equal(scaleEquityUnits(4455.267, "unknown"), 4455.267 * 1e6);

  const empty = computeFundamentals({
    equity: null,
    lastPrice: 10,
    marketCap: 1e9,
    profit: 1e8,
  });
  assert.equal(empty.nav, null);
  assert.equal(empty.price_to_book, null);
  assert.equal(empty.roe_pct, null);

  const low = computeFundamentals({
    equity: {
      equity: 100,
      equity_scale: "millions",
      equity_confidence: "low",
      equity_as_of: "2024-12-31",
      equity_currency: "LKR",
    },
    lastPrice: 10,
    marketCap: 2e8,
    profit: 1e7,
  });
  assert.equal(low.nav, null);

  const ok = computeFundamentals({
    equity: {
      equity: 100,
      equity_scale: "millions",
      equity_confidence: "high",
      equity_as_of: "2024-12-31",
      equity_currency: "LKR",
    },
    lastPrice: 10,
    marketCap: 200_000_000,
    profit: 20_000_000,
  });
  assert.equal(ok.nav, 100_000_000);
  assert.ok(ok.price_to_book != null && Math.abs(ok.price_to_book - 2) < 1e-9);
  assert.ok(ok.roe_pct != null && Math.abs(ok.roe_pct - 20) < 1e-9);
}

function testSplitAdjust() {
  assert.ok(Math.abs(adjustFactor(1, 3) - 1 / 3) < 1e-12);
  const bars = [
    {
      trade_date: "2026-04-08",
      open: 128,
      high: 130,
      low: 126,
      close: 127.75,
      volume: 1000,
    },
    {
      trade_date: "2026-04-09",
      open: 46,
      high: 48,
      low: 45,
      close: 46.3,
      volume: 2000,
    },
  ];
  const adjusted = adjustBarsForSplits(bars, [
    {
      effective_date: "2026-04-09",
      kind: "split",
      ratio_from: 1,
      ratio_to: 3,
    },
  ]);
  assert.ok(Math.abs(adjusted[0]!.close - 127.75 / 3) < 1e-9);
  assert.equal(adjusted[1]!.close, 46.3);
  // 1Y-style return across the cliff should not be ~−64% after adjust.
  const rets = computePeriodReturns(
    closesFromBars(adjusted),
    adjusted,
  );
  // Only 2 points — short horizons null; just assert continuity of closes.
  assert.ok(adjusted[0]!.close < 50);
  assert.ok(rets["1W"] == null);
}

testPeriodReturns();
testTechLabels();
testFundamentalsHonesty();
testSplitAdjust();
console.log("WEB_PERIOD_TECH_UNIT_OK");
