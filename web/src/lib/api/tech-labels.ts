/**
 * Thin technical *labels* from daily OHLC — symbol detail only.
 * Not a screener column farm. Research / NFA.
 */

import { toFiniteNumber } from "@/lib/api/finite-number";

export type TechBar = {
  high: number;
  low: number;
  close: number;
};

export type TechLabels = {
  sma50_pct: number | null;
  atr_pct: number | null;
  macd_bias: "BULL" | "BEAR" | null;
  bb_pos: "▲" | "▼" | "SQZ" | "•" | null;
  week52_pct: number | null;
};

function sma(values: number[], period: number): number | null {
  if (values.length < period) return null;
  let sum = 0;
  for (let i = values.length - period; i < values.length; i++) {
    sum += values[i]!;
  }
  const m = sum / period;
  return Number.isFinite(m) ? m : null;
}

function emaSeries(values: number[], period: number): number[] {
  if (values.length === 0) return [];
  const k = 2 / (period + 1);
  const out: number[] = [];
  let prev = values[0]!;
  out.push(prev);
  for (let i = 1; i < values.length; i++) {
    prev = values[i]! * k + prev * (1 - k);
    out.push(prev);
  }
  return out;
}

function atrPct(bars: TechBar[], period = 14): number | null {
  if (bars.length < period + 1) return null;
  const trs: number[] = [];
  for (let i = 1; i < bars.length; i++) {
    const h = bars[i]!.high;
    const l = bars[i]!.low;
    const prevClose = bars[i - 1]!.close;
    const tr = Math.max(h - l, Math.abs(h - prevClose), Math.abs(l - prevClose));
    if (Number.isFinite(tr) && tr >= 0) trs.push(tr);
  }
  if (trs.length < period) return null;
  const slice = trs.slice(-period);
  const atr = slice.reduce((a, b) => a + b, 0) / period;
  const last = bars[bars.length - 1]!.close;
  if (!Number.isFinite(atr) || !Number.isFinite(last) || last <= 0) return null;
  return (atr / last) * 100;
}

function macdBias(closes: number[]): "BULL" | "BEAR" | null {
  if (closes.length < 35) return null;
  const ema12 = emaSeries(closes, 12);
  const ema26 = emaSeries(closes, 26);
  const macdLine: number[] = [];
  for (let i = 0; i < closes.length; i++) {
    macdLine.push(ema12[i]! - ema26[i]!);
  }
  const signal = emaSeries(macdLine, 9);
  const last = macdLine[macdLine.length - 1]! - signal[signal.length - 1]!;
  if (!Number.isFinite(last)) return null;
  return last >= 0 ? "BULL" : "BEAR";
}

function bbPos(closes: number[], period = 20): TechLabels["bb_pos"] {
  if (closes.length < period) return null;
  const slice = closes.slice(-period);
  const mean = slice.reduce((a, b) => a + b, 0) / period;
  let varSum = 0;
  for (const v of slice) varSum += (v - mean) ** 2;
  const std = Math.sqrt(varSum / period);
  if (!Number.isFinite(mean) || !Number.isFinite(std)) return null;
  const last = closes[closes.length - 1]!;
  const width = mean === 0 ? 0 : (2 * std) / Math.abs(mean);
  if (width < 0.04) return "SQZ";
  const upper = mean + 2 * std;
  const lower = mean - 2 * std;
  if (last >= upper) return "▲";
  if (last <= lower) return "▼";
  return "•";
}

export function barsFromDaily(
  rows: {
    high?: unknown;
    low?: unknown;
    close?: unknown;
    price?: unknown;
  }[],
): TechBar[] {
  const out: TechBar[] = [];
  for (const r of rows) {
    const close = toFiniteNumber(r.close ?? r.price);
    if (close == null || close <= 0) continue;
    let high = toFiniteNumber(r.high);
    let low = toFiniteNumber(r.low);
    if (high == null || high <= 0) high = close;
    if (low == null || low <= 0) low = close;
    if (high < low) {
      const t = high;
      high = low;
      low = t;
    }
    out.push({ high, low, close });
  }
  return out;
}

export function computeTechLabels(barsAsc: TechBar[]): TechLabels {
  const closes = barsAsc.map((b) => b.close);
  const last = closes[closes.length - 1];
  const s50 = sma(closes, 50);
  let sma50_pct: number | null = null;
  if (last != null && s50 != null && s50 !== 0) {
    const pct = ((last - s50) / Math.abs(s50)) * 100;
    sma50_pct = Number.isFinite(pct) ? pct : null;
  }
  let week52_pct: number | null = null;
  if (closes.length >= 20 && last != null) {
    const window = closes.slice(-Math.min(252, closes.length));
    const lo = Math.min(...window);
    const hi = Math.max(...window);
    if (hi > lo && Number.isFinite(lo) && Number.isFinite(hi)) {
      week52_pct = ((last - lo) / (hi - lo)) * 100;
    }
  }
  return {
    sma50_pct,
    atr_pct: atrPct(barsAsc),
    macd_bias: macdBias(closes),
    bb_pos: bbPos(closes),
    week52_pct: week52_pct != null && Number.isFinite(week52_pct) ? week52_pct : null,
  };
}
