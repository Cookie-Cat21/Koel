/**
 * Appetite MAX stitch + aggregate helpers.
 * Invoked via npx tsx from web/ after staging.
 */
import assert from "node:assert/strict";

import {
  aggregateAppetiteSeries,
  chooseAggregateMode,
  monthBucketKey,
  stitchHybridWithCse,
  weekBucketKey,
} from "./src/components/appetite/appetite-history-chart.tsx";
import type { AppetiteDay } from "./src/lib/api/appetite.ts";

function day(trade_date: string, score: number): AppetiteDay {
  return {
    trade_date,
    score,
    band: "neutral",
    components: {
      breadth: null,
      intensity: null,
      index: null,
      participation: null,
    },
    source: "cse",
    universe_n: 200,
    advancers: null,
    decliners: null,
    unchanged: null,
    aspi_change_pct: null,
    computed_at: null,
  };
}

function testStitch() {
  const hybrid = [
    day("2025-01-02", 40),
    day("2025-10-06", 55),
  ];
  const cse = [
    day("2025-09-01", 50),
    day("2025-10-06", 55),
    day("2025-10-07", 60),
    day("2026-07-17", 22),
  ];
  const out = stitchHybridWithCse(hybrid, cse);
  assert.equal(out.length, 4);
  assert.equal(out[0]!.trade_date, "2025-01-02");
  assert.equal(out[1]!.trade_date, "2025-10-06");
  assert.equal(out[2]!.trade_date, "2025-10-07");
  assert.equal(out[3]!.trade_date, "2026-07-17");

  assert.deepEqual(stitchHybridWithCse([], cse), cse);
  assert.equal(stitchHybridWithCse(hybrid, []).length, 2);
}

function testAggregate() {
  assert.equal(monthBucketKey("2020-03-15"), "2020-03");
  assert.equal(weekBucketKey("2020-01-06")?.startsWith("2020-W"), true);

  assert.equal(chooseAggregateMode(100), "none");
  assert.equal(chooseAggregateMode(400), "week");
  assert.equal(chooseAggregateMode(6000), "month");

  const jan = [
    day("2020-01-02", 10),
    day("2020-01-15", 30),
    day("2020-01-31", 50),
    day("2020-02-03", 70),
    day("2020-02-28", 90),
  ];
  const monthly = aggregateAppetiteSeries(jan, "month");
  assert.equal(monthly.length, 2);
  // First month avg (10+30+50)/3 = 30
  assert.ok(Math.abs(monthly[0]!.score - 30) < 1e-9);
  // Tip fidelity — last point is raw tip, not Feb avg
  assert.equal(monthly[1]!.trade_date, "2020-02-28");
  assert.equal(monthly[1]!.score, 90);

  assert.equal(aggregateAppetiteSeries(jan, "none").length, 5);
}

testStitch();
testAggregate();
console.log("WEB_APPETITE_MAX_UNIT_OK");
