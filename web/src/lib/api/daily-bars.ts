/**
 * Daily OHLC helpers for candlestick charts (Postgres ``daily_bars``).
 * Client-safe sanitizers — no ``pg`` import.
 */

import { toFiniteNumber } from "@/lib/api/finite-number";

export const MAX_DAILY_BARS_LIMIT = 400;
export const DEFAULT_DAILY_BARS_LIMIT = 260;

export type DailyBarPoint = {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
};

/**
 * Normalize a DB row into a chartable candle.
 * When open/high/low are missing, synthesize a flat candle from close.
 */
export function normalizeDailyBar(row: {
  trade_date: unknown;
  open?: unknown;
  high?: unknown;
  low?: unknown;
  price?: unknown;
  close?: unknown;
  volume?: unknown;
}): DailyBarPoint | null {
  let tradeDate: string | null = null;
  if (row.trade_date instanceof Date) {
    tradeDate = row.trade_date.toISOString().slice(0, 10);
  } else if (typeof row.trade_date === "string") {
    tradeDate = row.trade_date.slice(0, 10);
  }
  if (!tradeDate || !/^\d{4}-\d{2}-\d{2}$/.test(tradeDate)) return null;

  const close = toFiniteNumber(row.close ?? row.price);
  if (close == null || close <= 0) return null;

  let open = toFiniteNumber(row.open);
  let high = toFiniteNumber(row.high);
  let low = toFiniteNumber(row.low);
  if (open == null || open <= 0) open = close;
  if (high == null || high <= 0) high = Math.max(open, close);
  if (low == null || low <= 0) low = Math.min(open, close);
  // Enforce OHLC invariants after null fill.
  high = Math.max(high, open, close);
  low = Math.min(low, open, close);

  return {
    trade_date: tradeDate,
    open,
    high,
    low,
    close,
    volume: toFiniteNumber(row.volume),
  };
}

/** Sessions for range chips (approx trading days). */
export function sessionsForRange(range: "1M" | "3M" | "6M" | "1Y"): number {
  switch (range) {
    case "1M":
      return 22;
    case "3M":
      return 66;
    case "6M":
      return 132;
    case "1Y":
    default:
      return 260;
  }
}
