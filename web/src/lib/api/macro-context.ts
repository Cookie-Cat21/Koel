/**
 * Context macros from `macro_series` (Postgres only).
 * Flag-gated adapters write rows; UI fails soft when empty.
 */

import type { Pool } from "pg";

import { toFiniteNumber } from "@/lib/api/finite-number";
import { toIso } from "@/lib/api/time";

export type MacroPoint = {
  ts: string | null;
  as_of_date: string | null;
  value: number;
  unit: string | null;
  attribution: string;
  source: string;
  series_id: string;
};

export type MacroSeriesCard = {
  series_id: string;
  latest: MacroPoint | null;
  history: MacroPoint[];
  delta_pct: number | null;
};

function asDateIso(raw: unknown): string | null {
  if (raw instanceof Date && !Number.isNaN(raw.getTime())) {
    return raw.toISOString().slice(0, 10);
  }
  if (typeof raw === "string") {
    const m = raw.match(/^(\d{4}-\d{2}-\d{2})/);
    return m ? m[1]! : null;
  }
  return null;
}

function parsePoint(row: Record<string, unknown>): MacroPoint | null {
  const value = toFiniteNumber(row.value);
  if (value == null) return null;
  const series_id = typeof row.series_id === "string" ? row.series_id : "";
  const source = typeof row.source === "string" ? row.source : "";
  if (!series_id || !source) return null;
  return {
    ts: toIso(row.ts),
    as_of_date: asDateIso(row.as_of_date),
    value,
    unit: typeof row.unit === "string" ? row.unit : null,
    attribution: typeof row.attribution === "string" ? row.attribution : "",
    source,
    series_id,
  };
}

/** True when attribution marks a demo / fixture row (not live ingest). */
export function isDemoMacroAttribution(attribution: string | null | undefined): boolean {
  if (typeof attribution !== "string") return false;
  return /demo\s*seed/i.test(attribution);
}

export async function queryMacroSeries(
  pool: Pool,
  seriesId: string,
  limit = 90,
): Promise<MacroSeriesCard> {
  const lim = Math.min(Math.max(limit, 1), 500);
  try {
    // Prefer live ingest; demo-seed fixtures must not shadow real CBSL/EIA rows.
    const res = await pool.query(
      `SELECT source, series_id, ts, value, unit, as_of_date, attribution
       FROM macro_series
       WHERE series_id = $1
         AND attribution NOT ILIKE '%demo seed%'
       ORDER BY ts DESC
       LIMIT $2`,
      [seriesId, lim],
    );
    const desc = res.rows
      .map((r) => parsePoint(r as Record<string, unknown>))
      .filter((p): p is MacroPoint => p != null);
    const history = [...desc].reverse();
    const latest = desc[0] ?? null;
    let delta_pct: number | null = null;
    if (desc.length >= 2) {
      const a = desc[0]!.value;
      const b = desc[1]!.value;
      if (b !== 0 && Number.isFinite(a) && Number.isFinite(b)) {
        delta_pct = ((a - b) / Math.abs(b)) * 100;
      }
    }
    return { series_id: seriesId, latest, history, delta_pct };
  } catch {
    // Table missing / migrate pending — fail soft.
    return { series_id: seriesId, latest: null, history: [], delta_pct: null };
  }
}

export type ContextBundle = {
  usd_lkr: MacroSeriesCard;
  eur_lkr: MacroSeriesCard;
  brent: MacroSeriesCard;
  wti: MacroSeriesCard;
  tourism_arrivals: MacroSeriesCard;
  food_pressure: MacroSeriesCard;
};

export async function queryContextBundle(pool: Pool): Promise<ContextBundle> {
  const [
    usd_lkr,
    eur_lkr,
    brent,
    wti,
    tourism_arrivals,
    food_pressure,
  ] = await Promise.all([
    queryMacroSeries(pool, "USD_LKR", 120),
    queryMacroSeries(pool, "EUR_LKR", 120),
    queryMacroSeries(pool, "BRENT_SPOT", 120),
    queryMacroSeries(pool, "WTI_SPOT", 120),
    queryMacroSeries(pool, "TOURISM_ARRIVALS", 36),
    queryMacroSeries(pool, "FOOD_PRESSURE", 52),
  ]);
  return { usd_lkr, eur_lkr, brent, wti, tourism_arrivals, food_pressure };
}
