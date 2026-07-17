/**
 * Model / forecast health queries — Postgres only, research metrics (NFA).
 */

import type { Pool } from "pg";

import { toFiniteNumber } from "@/lib/api/finite-number";
import { toIso } from "@/lib/api/time";

export type MlHealthPayload = {
  champion: {
    model_id: string;
    oos_hit: number | null;
    oos_gated_hit: number | null;
    oos_coverage: number | null;
    status: string;
  } | null;
  scoreboard: {
    hit_20d: number | null;
    hit_60d: number | null;
    gated_hit_20d: number | null;
    n_scored_60d: number;
  };
  accrual: {
    market_summary_days: number;
    order_book_snapshots: number;
    latest_order_book_at: string | null;
    forecast_points_latest_as_of: string | null;
    spoke_symbols_latest: number;
  };
  disclaimer: string;
};

function hitRate(rows: { hit: boolean | null }[]): number | null {
  const usable = rows.filter((r) => r.hit === true || r.hit === false);
  if (usable.length === 0) return null;
  return usable.filter((r) => r.hit === true).length / usable.length;
}

export async function queryMlHealth(pool: Pool): Promise<MlHealthPayload> {
  let champion: MlHealthPayload["champion"] = null;
  try {
    const champ = await pool.query<{
      model_id: string;
      oos_hit: number | null;
      oos_gated_hit: number | null;
      oos_coverage: number | null;
      status: string;
    }>(
      `
      SELECT model_id, oos_hit, oos_gated_hit, oos_coverage, status
      FROM model_registry
      WHERE status = 'champion'
      ORDER BY promoted_at DESC NULLS LAST, created_at DESC
      LIMIT 1
      `,
    );
    if (champ.rowCount && champ.rows[0]) {
      const r = champ.rows[0];
      champion = {
        model_id: String(r.model_id).slice(0, 128),
        oos_hit: toFiniteNumber(r.oos_hit),
        oos_gated_hit: toFiniteNumber(r.oos_gated_hit),
        oos_coverage: toFiniteNumber(r.oos_coverage),
        status: String(r.status).slice(0, 32),
      };
    }
  } catch {
    champion = null;
  }

  let hit20: number | null = null;
  let hit60: number | null = null;
  let gated20: number | null = null;
  let n60 = 0;
  try {
    const scored = await pool.query<{
      issued_at: Date | string;
      hit: boolean | null;
      confidence: number | null;
    }>(
      `
      SELECT issued_at, hit, confidence
      FROM forecast_outcomes
      WHERE scored = TRUE
        AND issued_at >= (CURRENT_DATE - INTERVAL '60 days')
      `,
    );
    n60 = scored.rowCount ?? 0;
    const rows = scored.rows;
    const cutoff20 = new Date();
    cutoff20.setUTCDate(cutoff20.getUTCDate() - 20);
    const in20 = rows.filter((r) => {
      const d =
        r.issued_at instanceof Date
          ? r.issued_at
          : new Date(String(r.issued_at));
      return Number.isFinite(d.getTime()) && d >= cutoff20;
    });
    hit60 = hitRate(rows);
    hit20 = hitRate(in20);
    gated20 = hitRate(
      in20.filter(
        (r) =>
          typeof r.confidence === "number" &&
          Number.isFinite(r.confidence) &&
          r.confidence >= 0.55,
      ),
    );
  } catch {
    // tables may be missing in fresh envs
  }

  let marketDays = 0;
  let obCount = 0;
  let latestOb: string | null = null;
  let forecastAsOf: string | null = null;
  let spoke = 0;
  try {
    const mkt = await pool.query<{ n: string | number }>(
      `SELECT COUNT(*)::int AS n FROM market_daily_summary`,
    );
    marketDays = Number(mkt.rows[0]?.n ?? 0) || 0;
  } catch {
    marketDays = 0;
  }
  try {
    const ob = await pool.query<{ n: string | number; mx: Date | string | null }>(
      `
      SELECT COUNT(*)::int AS n, MAX(ts) AS mx
      FROM order_book_snapshots
      `,
    );
    obCount = Number(ob.rows[0]?.n ?? 0) || 0;
    latestOb = toIso(ob.rows[0]?.mx ?? null);
  } catch {
    obCount = 0;
  }
  try {
    const fp = await pool.query<{
      as_of: Date | string | null;
      spoke: string | number;
    }>(
      `
      SELECT
        (SELECT MAX(as_of) FROM forecast_points) AS as_of,
        COUNT(DISTINCT symbol)::int AS spoke
      FROM forecast_points
      WHERE as_of = (SELECT MAX(as_of) FROM forecast_points)
        AND gate IN ('gated_p90', 'hpe_p90', 'gated_c55', 'gated')
      `,
    );
    const raw = fp.rows[0]?.as_of;
    if (raw instanceof Date) {
      forecastAsOf = raw.toISOString().slice(0, 10);
    } else if (typeof raw === "string") {
      forecastAsOf = raw.slice(0, 10);
    }
    spoke = Number(fp.rows[0]?.spoke ?? 0) || 0;
  } catch {
    forecastAsOf = null;
    spoke = 0;
  }

  return {
    champion,
    scoreboard: {
      hit_20d: hit20,
      hit_60d: hit60,
      gated_hit_20d: gated20,
      n_scored_60d: n60,
    },
    accrual: {
      market_summary_days: marketDays,
      order_book_snapshots: obCount,
      latest_order_book_at: latestOb,
      forecast_points_latest_as_of: forecastAsOf,
      spoke_symbols_latest: spoke,
    },
    disclaimer:
      "Research / ops metrics only — historical OOS calibration, not financial advice.",
  };
}
