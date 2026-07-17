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

/**
 * How many raw sessions/ticks to load for a range chip.
 * 1D = snapshot ticks; others = daily_bars tail length.
 * Sized so fit-width expand slots stay ~10–14px (not huge candles).
 */
export function sessionsForRange(range: ChartRangeKey): number {
  switch (range) {
    case "1D":
      return 240; // bucket into ~72 intraday candles
    case "1M":
      return 80; // denser month view (~4 trading months of path)
    case "3M":
      return 100;
    case "6M":
      return 160;
    case "1Y":
    default:
      return 260;
  }
}

/**
 * Target candle count after aggregation for fit-width charts.
 * More candles ⇒ smaller bodies when the plot fills the dialog.
 */
export function displayCandlesForRange(range: ChartRangeKey): number {
  switch (range) {
    case "1D":
      return 72;
    case "1M":
      return 80;
    case "3M":
      return 100;
    case "6M":
      return 140;
    case "1Y":
    default:
      return 200;
  }
}

/** Hero strip under the quote — denser pack at fixed pitch. */
export const HERO_DISPLAY_CANDLES = 80;

/**
 * Build intraday OHLC candles from tick prices for the 1D expand view.
 * Buckets by equal count when timestamps are sparse/missing.
 */
/**
 * Downsample dense daily series into fewer OHLC candles for readable charts.
 * CSE 1Y ≈ 240 sessions — rendering all as 2px sticks looks like a barcode.
 */
export function aggregateBarsForDisplay(
  bars: DailyBarPoint[],
  maxCandles = 72,
): DailyBarPoint[] {
  if (bars.length <= maxCandles) return bars;
  const chunk = Math.ceil(bars.length / maxCandles);
  const out: DailyBarPoint[] = [];
  for (let i = 0; i < bars.length; i += chunk) {
    const slice = bars.slice(i, i + chunk);
    if (slice.length === 0) continue;
    const first = slice[0]!;
    const last = slice[slice.length - 1]!;
    const open = first.open ?? first.close;
    let high = -Infinity;
    let low = Infinity;
    let vol: number | null = null;
    for (const b of slice) {
      if (b.high > high) high = b.high;
      if (b.low < low) low = b.low;
      if (b.volume != null) vol = (vol ?? 0) + b.volume;
    }
    if (!Number.isFinite(high) || !Number.isFinite(low)) {
      high = Math.max(open, last.close);
      low = Math.min(open, last.close);
    }
    out.push({
      trade_date: last.trade_date,
      open,
      high,
      low,
      close: last.close,
      volume: vol,
    });
  }
  return out;
}

export function ticksToIntradayBars(
  ticks: { ts: string | null; price: number }[],
  targetCandles = 40,
): DailyBarPoint[] {
  const clean = ticks
    .filter(
      (t) =>
        typeof t.price === "number" && Number.isFinite(t.price) && t.price > 0,
    )
    .slice()
    .sort((a, b) => {
      const ta = a.ts ? Date.parse(a.ts) : NaN;
      const tb = b.ts ? Date.parse(b.ts) : NaN;
      if (Number.isFinite(ta) && Number.isFinite(tb)) return ta - tb;
      return 0;
    });
  if (clean.length < 2) return [];

  // Prefer ~2–3 ticks per candle so bodies have room to move.
  const n = Math.max(
    4,
    Math.min(targetCandles, Math.floor(clean.length / 2)),
  );
  const chunk = Math.max(2, Math.ceil(clean.length / n));
  const out: DailyBarPoint[] = [];

  for (let i = 0; i < clean.length; i += chunk) {
    const slice = clean.slice(i, i + chunk);
    if (slice.length === 0) continue;
    const prices = slice.map((t) => t.price);
    const open = prices[0]!;
    const close = prices[prices.length - 1]!;
    let high = Math.max(...prices);
    let low = Math.min(...prices);
    // Ensure a visible wick even when flat (pure mark-to-mark ticks).
    if (high === low) {
      const pad = Math.max(high * 0.001, 0.01);
      high += pad;
      low = Math.max(0.01, low - pad);
    }
    const lastTs = slice[slice.length - 1]?.ts;
    let tradeDate = `t${String(out.length).padStart(2, "0")}`;
    if (typeof lastTs === "string" && lastTs.length >= 16) {
      const d = new Date(lastTs);
      if (Number.isFinite(d.getTime())) {
        try {
          tradeDate = d.toLocaleTimeString("en-GB", {
            timeZone: "Asia/Colombo",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          });
        } catch {
          tradeDate = d.toISOString().slice(11, 16);
        }
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
