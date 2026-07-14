import {
  finiteSparklinePoints,
  MAX_SPARKLINE_POINTS,
} from "@/lib/sparkline";

export const MAX_COMPARE_SYMBOLS = 4;

export type ComparePoint = { ts: string | null; price: number };
export type CompareSeries = { symbol: string; points: ComparePoint[] };

export type CompareScaleMode = "indexed" | "price";

/** Chart row: label + one numeric column per series key. */
export type CompareChartRow = {
  t: string;
  ts: string | null;
} & Record<string, string | number | null>;

/**
 * Safe Recharts / CSS var key — CSE symbols contain ``.`` which breaks
 * ``--color-JKH.N0000`` custom properties.
 */
export function compareSeriesKey(symbol: string): string {
  return symbol.replace(/[^A-Za-z0-9]+/g, "_");
}

/**
 * Rebase each series so the first finite price = 100 (fair overlay when
 * absolute LKR levels differ). Price mode keeps raw LKR.
 */
export function buildCompareChartRows(
  series: CompareSeries[],
  mode: CompareScaleMode,
): CompareChartRow[] {
  if (!Array.isArray(series) || series.length === 0) return [];

  const prepared = series.slice(0, MAX_COMPARE_SYMBOLS).map((s) => {
    const points = finiteSparklinePoints(
      Array.isArray(s.points) ? s.points.slice(0, MAX_SPARKLINE_POINTS) : [],
    );
    const base = points[0]?.price;
    const values =
      mode === "indexed" && base != null && base !== 0
        ? points.map((p) => ({
            ts: p.ts,
            value: (p.price / base) * 100,
          }))
        : points.map((p) => ({ ts: p.ts, value: p.price }));
    return { symbol: s.symbol, key: compareSeriesKey(s.symbol), values };
  });

  const maxLen = Math.max(0, ...prepared.map((s) => s.values.length));
  if (maxLen < 2) return [];

  const rows: CompareChartRow[] = [];
  for (let i = 0; i < maxLen; i++) {
    const anchor =
      prepared.find((s) => s.values[i]?.ts)?.values[i]?.ts ?? null;
    const row: CompareChartRow = {
      t: formatCompareTick(anchor, i, maxLen),
      ts: anchor,
    };
    for (const s of prepared) {
      const v = s.values[i]?.value;
      row[s.key] =
        v != null && Number.isFinite(v) ? Number(v.toFixed(4)) : null;
    }
    rows.push(row);
  }
  return rows;
}

function formatCompareTick(
  ts: string | null,
  index: number,
  total: number,
): string {
  if (typeof ts === "string" && ts.length >= 16) {
    // Prefer HH:MM for dense intraday; fall back to date slice.
    const time = ts.slice(11, 16);
    if (/^\d{2}:\d{2}$/.test(time)) return time;
    return ts.slice(0, 10);
  }
  if (total <= 1) return "0";
  return String(index);
}
