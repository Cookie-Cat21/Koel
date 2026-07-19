/**
 * Leaderboard rank helpers for Signal Board Δ.
 * Rank 1 = highest score. rank_delta = prior_rank - rank (+ = rose).
 */

export type Rankable = {
  symbol: string;
  score: number | null;
};

export type RankDelta = {
  rank: number;
  prior_rank: number | null;
  rank_delta: number | null;
};

/** Stable high→low score order (symbol tie-break). */
export function sortByScoreDesc<T extends Rankable>(rows: T[]): T[] {
  return [...rows].sort((a, b) => {
    const sa = a.score ?? Number.NEGATIVE_INFINITY;
    const sb = b.score ?? Number.NEGATIVE_INFINITY;
    if (sb !== sa) return sb - sa;
    return a.symbol.localeCompare(b.symbol);
  });
}

/** Assign 1-based positions after score sort. */
export function ranksBySymbol(rows: Rankable[]): Map<string, number> {
  const sorted = sortByScoreDesc(rows);
  const out = new Map<string, number>();
  sorted.forEach((row, i) => {
    out.set(row.symbol, i + 1);
  });
  return out;
}

/**
 * Attach current rank + Δ vs a prior board.
 * Missing prior → prior_rank/rank_delta null (UI shows "new" when wanted).
 */
export function attachRankDeltas(
  current: Rankable[],
  prior: Rankable[],
): Map<string, RankDelta> {
  const currentRanks = ranksBySymbol(current);
  const priorRanks = ranksBySymbol(prior);
  const out = new Map<string, RankDelta>();
  for (const [symbol, rank] of currentRanks) {
    const priorRank = priorRanks.get(symbol) ?? null;
    out.set(symbol, {
      rank,
      prior_rank: priorRank,
      rank_delta: priorRank == null ? null : priorRank - rank,
    });
  }
  return out;
}
