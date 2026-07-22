/**
 * Client-side indicator math for koel Layer A (TradingView-inspired, not Pine).
 * Operates on close arrays oldest → newest.
 */

export type IndicatorPoint = {
  /** Index into the bars array (aligned). */
  index: number;
  value: number;
};

export type BandPoint = {
  index: number;
  mid: number;
  upper: number;
  lower: number;
};

function smaAt(closes: readonly number[], end: number, period: number): number | null {
  if (end + 1 < period) return null;
  let sum = 0;
  for (let i = end - period + 1; i <= end; i++) {
    const v = closes[i];
    if (v == null || !Number.isFinite(v)) return null;
    sum += v;
  }
  return sum / period;
}

export function computeSma(
  closes: readonly number[],
  period: number,
): IndicatorPoint[] {
  const out: IndicatorPoint[] = [];
  for (let i = 0; i < closes.length; i++) {
    const v = smaAt(closes, i, period);
    if (v != null) out.push({ index: i, value: v });
  }
  return out;
}

export function computeEma(
  closes: readonly number[],
  period: number,
): IndicatorPoint[] {
  const out: IndicatorPoint[] = [];
  if (closes.length < period || period < 1) return out;
  const k = 2 / (period + 1);
  let ema: number | null = smaAt(closes, period - 1, period);
  if (ema == null) return out;
  out.push({ index: period - 1, value: ema });
  for (let i = period; i < closes.length; i++) {
    const c = closes[i];
    if (c == null || !Number.isFinite(c)) continue;
    ema = c * k + ema * (1 - k);
    out.push({ index: i, value: ema });
  }
  return out;
}

export function computeBollinger(
  closes: readonly number[],
  period = 20,
  mult = 2,
): BandPoint[] {
  const out: BandPoint[] = [];
  for (let i = 0; i < closes.length; i++) {
    const mid = smaAt(closes, i, period);
    if (mid == null) continue;
    let sumSq = 0;
    for (let j = i - period + 1; j <= i; j++) {
      const v = closes[j]!;
      sumSq += (v - mid) * (v - mid);
    }
    const std = Math.sqrt(sumSq / period);
    out.push({
      index: i,
      mid,
      upper: mid + mult * std,
      lower: mid - mult * std,
    });
  }
  return out;
}

/** Wilder RSI. */
export function computeRsi(
  closes: readonly number[],
  period = 14,
): IndicatorPoint[] {
  const out: IndicatorPoint[] = [];
  if (closes.length <= period) return out;
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const d = closes[i]! - closes[i - 1]!;
    if (d >= 0) avgGain += d;
    else avgLoss -= d;
  }
  avgGain /= period;
  avgLoss /= period;
  const rsi0 =
    avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  out.push({ index: period, value: rsi0 });
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i]! - closes[i - 1]!;
    const gain = d > 0 ? d : 0;
    const loss = d < 0 ? -d : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    const rsi =
      avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
    out.push({ index: i, value: rsi });
  }
  return out;
}

export type KoelIndicatorFlags = {
  sma20: boolean;
  sma50: boolean;
  ema12: boolean;
  bb: boolean;
  rsi: boolean;
};

export const DEFAULT_INDICATORS: KoelIndicatorFlags = {
  sma20: true,
  sma50: false,
  ema12: false,
  bb: false,
  rsi: false,
};
