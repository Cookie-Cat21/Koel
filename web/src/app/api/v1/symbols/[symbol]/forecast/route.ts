import type { NextRequest } from "next/server";

import { toFiniteNumber } from "@/lib/api/finite-number";
import { normalizeSymbolParam } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const MAX_FORECAST_POINTS = 30;

/**
 * GET /api/v1/symbols/{symbol}/forecast — latest model path estimates.
 * Overlay-only; not a price target. Session required. Postgres only.
 */
export async function GET(
  request: NextRequest,
  ctx: { params: Promise<{ symbol: string }> },
) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  const { symbol: raw } = await ctx.params;
  const symbol = normalizeSymbolParam(raw);
  if (!symbol) {
    return jsonError(400, "validation_error", "Invalid symbol.");
  }

  try {
    const pool = getPool();
    // Prefer selective gates (p90 / HPE / gated) over always-on when several
    // model_versions share as_of. Use ::date for as_of in the follow-up query —
    // node-pg Date params can shift calendar dates across TZ boundaries.
    const latest = await pool.query<{
      as_of: Date | string;
      model_version: string;
    }>(
      `
      SELECT as_of, model_version
      FROM forecast_points
      WHERE symbol = $1
      ORDER BY
        as_of DESC,
        CASE
          WHEN gate IN ('gated_p90', 'hpe_p90') THEN 0
          WHEN gate IN ('gated_ltr', 'gated_c55', 'gated') THEN 1
          WHEN confidence_band = 'high' THEN 2
          WHEN confidence_band = 'medium' THEN 3
          WHEN confidence_band = 'low' THEN 4
          ELSE 5
        END,
        confidence DESC NULLS LAST,
        computed_at DESC
      LIMIT 1
      `,
      [symbol],
    );
    if (latest.rowCount === 0) {
      return jsonOk({
        symbol,
        points: [],
        model_version: null,
        as_of: null,
        disclaimer: "Model estimate when available — not financial advice.",
      });
    }
    const asOfRaw = latest.rows[0]!.as_of;
    const modelVersion = latest.rows[0]!.model_version;
    let asOfKey: string;
    if (asOfRaw instanceof Date) {
      asOfKey = asOfRaw.toISOString().slice(0, 10);
    } else if (typeof asOfRaw === "string") {
      asOfKey = asOfRaw.slice(0, 10);
    } else {
      return jsonOk({
        symbol,
        points: [],
        model_version: null,
        as_of: null,
        disclaimer: "Model estimate when available — not financial advice.",
      });
    }
    const rows = await pool.query<{
      ts: Date | string;
      yhat: number;
      horizon_i: number;
      confidence: number | null;
      confidence_band: string | null;
      gate: string | null;
      reasons: unknown;
    }>(
      `
      SELECT ts, yhat, horizon_i, confidence, confidence_band, gate, reasons
      FROM forecast_points
      WHERE symbol = $1
        AND model_version = $2
        AND as_of = $3::date
      ORDER BY horizon_i ASC
      LIMIT $4
      `,
      [symbol, modelVersion, asOfKey, MAX_FORECAST_POINTS],
    );

    const points: {
      ts: string | null;
      price: number | null;
      horizon_i: number;
      confidence: number | null;
      confidence_band: string | null;
    }[] = [];
    let gate: string | null = null;
    let confidenceBand: string | null = null;
    let confidence: number | null = null;
    const reasons: string[] = [];
    for (const row of rows.rows) {
      const price = toFiniteNumber(row.yhat);
      if (price == null) continue;
      const conf = toFiniteNumber(row.confidence);
      points.push({
        ts: toIso(row.ts),
        price,
        horizon_i: row.horizon_i,
        confidence: conf,
        confidence_band:
          typeof row.confidence_band === "string" ? row.confidence_band : null,
      });
      if (gate == null && typeof row.gate === "string") gate = row.gate;
      if (confidenceBand == null && typeof row.confidence_band === "string") {
        confidenceBand = row.confidence_band;
      }
      if (confidence == null && conf != null) confidence = conf;
      if (Array.isArray(row.reasons)) {
        for (const r of row.reasons) {
          if (typeof r === "string" && r.trim() && reasons.length < 6) {
            reasons.push(r.trim());
          }
        }
      }
    }

    return jsonOk({
      symbol,
      points,
      model_version: typeof modelVersion === "string" ? modelVersion : null,
      as_of: asOfKey,
      gate,
      confidence,
      confidence_band: confidenceBand,
      reasons,
      disclaimer:
        "Dashed forecast is a model estimate — research only, not financial advice. Confidence is historical OOS calibration, not a guarantee.",
    });
  } catch (err) {
    console.error("GET /symbols/forecast failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
