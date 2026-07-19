/**
 * Multi-horizon returns from daily close series (Postgres ``daily_bars``).
 * Research / NFA — null when history is too short.
 */

import { toFiniteNumber } from "@/lib/api/finite-number";

export type PeriodReturnKey = "1W" | "1M" | "3M" | "1Y";

export type PeriodReturns = Record<PeriodReturnKey, number | null>;

/** Approximate trading sessions per horizon (CSE ~5/week). */
const SESSIONS: Record<PeriodReturnKey, number> = {
  "1W": 5,
  "1M": 22,
  "3M": 66,
  "1Y": 252,
};

/**
 * ``closes`` oldest → newest. Returns % change vs close ``sessions`` ago.
 */
export function returnPctAtHorizon(
  closes: number[],
  sessions: number,
): number | null {
  if (!Array.isArray(closes) || closes.length < 2) return null;
  const n = Math.max(1, Math.floor(sessions));
  if (closes.length <= n) return null;
  const latest = closes[closes.length - 1];
  const prior = closes[closes.length - 1 - n];
  if (
    latest == null ||
    prior == null ||
    !Number.isFinite(latest) ||
    !Number.isFinite(prior) ||
    prior === 0
  ) {
    return null;
  }
  const pct = ((latest - prior) / Math.abs(prior)) * 100;
  return Number.isFinite(pct) ? pct : null;
}

/** Extract ascending closes from daily-bar-like rows. */
export function closesFromBars(
  bars: { close?: unknown; price?: unknown }[],
): number[] {
  const out: number[] = [];
  for (const b of bars) {
    const c = toFiniteNumber(b.close ?? b.price);
    if (c != null && c > 0) out.push(c);
  }
  return out;
}

export function computePeriodReturns(closesAsc: number[]): PeriodReturns {
  return {
    "1W": returnPctAtHorizon(closesAsc, SESSIONS["1W"]),
    "1M": returnPctAtHorizon(closesAsc, SESSIONS["1M"]),
    "3M": returnPctAtHorizon(closesAsc, SESSIONS["3M"]),
    "1Y": returnPctAtHorizon(closesAsc, SESSIONS["1Y"]),
  };
}
