/**
 * Signal Board rank Δ helpers.
 * Invoked via npx tsx from web/ after staging.
 */
import assert from "node:assert/strict";

import {
  attachRankDeltas,
  ranksBySymbol,
  sortByScoreDesc,
} from "./src/lib/api/signal-ranks.ts";

function testSortAndRanks() {
  const rows = [
    { symbol: "B.N0000", score: 10 },
    { symbol: "A.N0000", score: 30 },
    { symbol: "C.N0000", score: 30 },
    { symbol: "D.N0000", score: null },
  ];
  const sorted = sortByScoreDesc(rows);
  assert.deepEqual(
    sorted.map((r) => r.symbol),
    ["A.N0000", "C.N0000", "B.N0000", "D.N0000"],
  );
  const ranks = ranksBySymbol(rows);
  assert.equal(ranks.get("A.N0000"), 1);
  assert.equal(ranks.get("C.N0000"), 2);
  assert.equal(ranks.get("B.N0000"), 3);
  assert.equal(ranks.get("D.N0000"), 4);
}

function testRankDeltas() {
  const current = [
    { symbol: "A.N0000", score: 50 },
    { symbol: "B.N0000", score: 40 },
    { symbol: "C.N0000", score: 30 },
    { symbol: "NEW.N0000", score: 20 },
  ];
  const prior = [
    { symbol: "B.N0000", score: 55 },
    { symbol: "A.N0000", score: 45 },
    { symbol: "C.N0000", score: 35 },
  ];
  const deltas = attachRankDeltas(current, prior);
  // A: was 2, now 1 → +1
  assert.deepEqual(deltas.get("A.N0000"), {
    rank: 1,
    prior_rank: 2,
    rank_delta: 1,
  });
  // B: was 1, now 2 → -1
  assert.deepEqual(deltas.get("B.N0000"), {
    rank: 2,
    prior_rank: 1,
    rank_delta: -1,
  });
  // C: was 3, now 3 → 0
  assert.deepEqual(deltas.get("C.N0000"), {
    rank: 3,
    prior_rank: 3,
    rank_delta: 0,
  });
  // NEW: no prior
  assert.deepEqual(deltas.get("NEW.N0000"), {
    rank: 4,
    prior_rank: null,
    rank_delta: null,
  });
}

function testEmptyPrior() {
  const deltas = attachRankDeltas(
    [{ symbol: "A.N0000", score: 1 }],
    [],
  );
  assert.deepEqual(deltas.get("A.N0000"), {
    rank: 1,
    prior_rank: null,
    rank_delta: null,
  });
}

testSortAndRanks();
testRankDeltas();
testEmptyPrior();
console.log("WEB_SIGNAL_RANKS_UNIT_OK");
