/**
 * Unit harness for period-returns + tech-labels helpers.
 * Invoked via npx tsx from tests/test_web_route_regressions.py
 */
import assert from "node:assert/strict";

import {
  closesFromBars,
  computePeriodReturns,
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

  const long = Array.from({ length: 300 }, (_, i) => 50 + i * 0.1);
  const rets = computePeriodReturns(long);
  assert.ok(rets["1W"] != null);
  assert.ok(rets["1M"] != null);
  assert.ok(rets["3M"] != null);
  assert.ok(rets["1Y"] != null);

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
  assert.equal(scaleEquityUnits(1, "units"), null);

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

testPeriodReturns();
testTechLabels();
testFundamentalsHonesty();
console.log("WEB_PERIOD_TECH_UNIT_OK");
