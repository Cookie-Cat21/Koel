/**
 * Daily OHLC helpers for candlestick charts (Postgres ``daily_bars``).
 * Client-safe sanitizers — no ``pg`` import.
 */

import { toFiniteNumber } from "@/lib/api/finite-number";

export const MAX_DAILY_BARS_LIMIT = 400;
export const DEFAULT_DAILY_BARS_LIMIT = 260;

export type DailyBarPoint = {
  trade_date: string;
  /** Null when CSE omitted open — chart colors vs previous close. */
  open: number | null;
  high: number;
  low: number;
  close: number;
  volume: number | null;
};

/**
 * Normalize a DB row into a chartable candle.
 * Keep ``open`` null when missing (CSE often omits it). High/low fall back
 * to close so wicks still render.
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

  const openRaw = toFiniteNumber(row.open);
  const open =
    openRaw != null && openRaw > 0 ? openRaw : null;
  let high = toFiniteNumber(row.high);
  let low = toFiniteNumber(row.low);
  if (high == null || high <= 0) high = close;
  if (low == null || low <= 0) low = close;
  // Enforce HL vs close (and open when present).
  const openForBound = open ?? close;
  high = Math.max(high, openForBound, close);
  low = Math.min(low, openForBound, close);

  return {
    trade_date: tradeDate,
    open,
    high,
    low,
    close,
    volume: toFiniteNumber(row.volume),
  };
}

/**
 * Body open for painting: real open, else previous close (CSE often nulls open).
 */
export function candleBodyOpen(
  bars: DailyBarPoint[],
  index: number,
): number {
  const b = bars[index];
  if (!b) return 0;
  if (b.open != null && b.open > 0) return b.open;
  if (index > 0) {
    const prev = bars[index - 1]?.close;
    if (prev != null && prev > 0) return prev;
  }
  return b.close;
}

export type ChartRangeKey = "1D" | "1M" | "3M" | "6M" | "1Y";

/** Sessions / ticks for range chips. 1D uses snapshot ticks, not daily bars. */
export function sessionsForRange(range: ChartRangeKey): number {
  switch (range) {
    case "1D":
      return 120; // recent realtime ticks
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

/**
 * Build intraday OHLC candles from tick prices for the 1D expand view.
 * Buckets by equal count when timestamps are sparse/missing.
 */
export function ticksToIntradayBars(
  ticks: { ts: string | null; price: number }[],
  targetCandles = 40,
): DailyBarPoint[] {
  const clean = ticks.filter(
    (t) => typeof t.price === "number" && Number.isFinite(t.price) && t.price > 0,
  );
  if (clean.length < 2) return [];

  const n = Math.max(2, Math.min(targetCandles, Math.floor(clean.length / 2)));
  const chunk = Math.max(1, Math.ceil(clean.length / n));
  const out: DailyBarPoint[] = [];

  for (let i = 0; i < clean.length; i += chunk) {
    const slice = clean.slice(i, i + chunk);
    if (slice.length === 0) continue;
    const prices = slice.map((t) => t.price);
    const open = prices[0]!;
    const close = prices[prices.length - 1]!;
    const high = Math.max(...prices);
    const low = Math.min(...prices);
    const lastTs = slice[slice.length - 1]?.ts;
    let tradeDate = `t${out.length}`;
    if (typeof lastTs === "string" && lastTs.length >= 16) {
      // Use time label HH:MM for intraday axis readability
      const d = new Date(lastTs);
      if (Number.isFinite(d.getTime())) {
        tradeDate = d.toISOString().slice(11, 16);
      }
    }
    out.push({
      trade_date: tradeDate,
      open,
      high,
      low,
      close,
      volume: null,
    });
  }
  return out;
}
