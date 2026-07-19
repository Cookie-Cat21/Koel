/**
 * Daily OHLC helpers for candlestick charts (Postgres ``daily_bars``).
 * Client-safe sanitizers — no ``pg`` import.
 */

import { toFiniteNumber } from "@/lib/api/finite-number";
import { MAX_SPARKLINE_POINTS } from "@/lib/sparkline";

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
  const open = openRaw != null && openRaw > 0 ? openRaw : null;
  let high = toFiniteNumber(row.high);
  let low = toFiniteNumber(row.low);
  if (high == null || high <= 0) high = close;
  if (low == null || low <= 0) low = close;
  if (high < low) {
    const tmp = high;
    high = low;
    low = tmp;
  }
  high = Math.max(high, close, open ?? close);
  low = Math.min(low, close, open ?? close);

  const vol = toFiniteNumber(row.volume);
  return {
    trade_date: tradeDate,
    open,
    high,
    low,
    close,
    volume: vol != null && vol >= 0 ? vol : null,
  };
}

export type ChartRangeKey = "1D" | "1M" | "3M" | "6M" | "1Y";

/**
 * How many raw sessions/ticks to load for a range chip.
 * 1D = snapshot ticks; others = daily_bars tail length.
 * Depths match chip labels (~22 trading days / month).
 */
export function sessionsForRange(range: ChartRangeKey): number {
  switch (range) {
    case "1D":
      return 240;
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
 * Target candle count after aggregation for fit-width charts.
 */
export function displayCandlesForRange(range: ChartRangeKey): number {
  switch (range) {
    case "1D":
      return 72;
    case "1M":
      return 22;
    case "3M":
      return 66;
    case "6M":
      return 120;
    case "1Y":
    default:
      return 180;
  }
}

/** Hero strip under the quote. */
export const HERO_DISPLAY_CANDLES = 80;

/** Minimum session ticks before expand 1D prefers intraday over daily path. */
export const MIN_TICKS_FOR_INTRADAY = 16;

/** Asia/Colombo calendar date ``YYYY-MM-DD`` for a timestamp. */
export function colomboDateKey(
  ts: string | null | undefined,
  now: Date = new Date(),
): string | null {
  const d =
    typeof ts === "string" && ts.trim()
      ? new Date(ts)
      : now;
  if (!Number.isFinite(d.getTime())) return null;
  try {
    return d.toLocaleDateString("en-CA", { timeZone: "Asia/Colombo" });
  } catch {
    return d.toISOString().slice(0, 10);
  }
}

/**
 * Keep ticks from the latest Colombo session day present in the series.
 * Used so 1D does not blend multiple trading days into one "Intraday" view.
 */
export function filterLatestColomboSession(
  ticks: { ts: string | null; price: number }[],
): { ts: string | null; price: number }[] {
  if (!Array.isArray(ticks) || ticks.length === 0) return [];
  let latestKey: string | null = null;
  for (const t of ticks) {
    const key = colomboDateKey(t.ts);
    if (!key) continue;
    if (latestKey == null || key > latestKey) latestKey = key;
  }
  if (!latestKey) return ticks.slice();
  return ticks.filter((t) => colomboDateKey(t.ts) === latestKey);
}

/**
 * True when the session day is today's Colombo calendar date.
 */
export function isColomboSessionToday(
  ticks: { ts: string | null }[],
  now: Date = new Date(),
): boolean {
  const today = colomboDateKey(null, now);
  if (!today) return false;
  for (let i = ticks.length - 1; i >= 0; i--) {
    const key = colomboDateKey(ticks[i]?.ts);
    if (key) return key === today;
  }
  return false;
}

/**
 * Short label for day-change scope next to last price.
 *
 * CSE ``change`` / ``change_pct`` are vs previous close for the snapshot's
 * session — not necessarily "today" when the market is closed or the tick is
 * from a prior Colombo calendar day. Returns ``today`` only when the stamp
 * falls on today's Asia/Colombo date; otherwise a short Colombo date
 * (e.g. ``Jul 17``) so weekends/stale ticks are not misleading.
 */
export function dayChangeScopeLabel(
  ts: string | null | undefined,
  now: Date = new Date(),
): string {
  if (typeof ts !== "string" || !ts.trim()) return "session";
  const snapKey = colomboDateKey(ts, now);
  const todayKey = colomboDateKey(null, now);
  if (!snapKey) return "session";
  if (todayKey && snapKey === todayKey) return "today";
  const d = new Date(ts);
  if (!Number.isFinite(d.getTime())) return "session";
  try {
    return d.toLocaleDateString("en-LK", {
      month: "short",
      day: "numeric",
      timeZone: "Asia/Colombo",
    });
  } catch {
    return "session";
  }
}

/**
 * Cap ascending tick series from the **end** so expand 1D keeps the newest
 * prints (``finiteSparklinePoints`` alone keeps the oldest 200).
 */
export function newestFiniteTicks(
  points: { ts: string | null; price: number | null | undefined }[],
  max = MAX_SPARKLINE_POINTS,
): { ts: string | null; price: number }[] {
  if (!Array.isArray(points) || points.length === 0) return [];
  const clean: { ts: string | null; price: number }[] = [];
  for (const p of points) {
    if (p == null || typeof p !== "object") continue;
    const price = toFiniteNumber(p.price);
    if (price == null || price <= 0) continue;
    clean.push({
      ts: typeof p.ts === "string" ? p.ts : null,
      price,
    });
  }
  if (clean.length <= max) return clean;
  return clean.slice(-max);
}

/**
 * Open for candle body coloring — prefer stored open, else prior close.
 */
export function candleBodyOpen(bars: DailyBarPoint[], index: number): number {
  const b = bars[index];
  if (!b) return 0;
  if (b.open != null && Number.isFinite(b.open) && b.open > 0) return b.open;
  if (index > 0) {
    const prev = bars[index - 1]!.close;
    if (Number.isFinite(prev) && prev > 0) return prev;
  }
  return b.close;
}

/**
 * Downsample dense daily series into fewer OHLC candles for readable charts.
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
    let high = -Infinity;
    let low = Infinity;
    let vol = 0;
    let volAny = false;
    for (const b of slice) {
      if (Number.isFinite(b.high)) high = Math.max(high, b.high);
      if (Number.isFinite(b.low)) low = Math.min(low, b.low);
      high = Math.max(high, b.close);
      low = Math.min(low, b.close);
      if (b.open != null) {
        high = Math.max(high, b.open);
        low = Math.min(low, b.open);
      }
      if (b.volume != null && Number.isFinite(b.volume)) {
        vol += b.volume;
        volAny = true;
      }
    }
    if (!Number.isFinite(high) || !Number.isFinite(low)) {
      high = Math.max(first.close, last.close);
      low = Math.min(first.close, last.close);
    }
    const open =
      first.open != null && first.open > 0 ? first.open : first.close;
    out.push({
      trade_date: last.trade_date,
      open,
      high,
      low,
      close: last.close,
      volume: volAny ? vol : null,
    });
  }
  return out;
}

/**
 * Build intraday OHLC candles from tick prices for the 1D expand view.
 * Bucket open = first print in the bucket; high/low from bucket prices only
 * (no synthetic pad — the renderer draws flat dojis).
 */
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
    const high = Math.max(...prices);
    const low = Math.min(...prices);
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
    // Disambiguate duplicate clock labels so React keys stay unique.
    if (out.some((b) => b.trade_date === tradeDate)) {
      tradeDate = `${tradeDate}:${String(out.length).padStart(2, "0")}`;
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
