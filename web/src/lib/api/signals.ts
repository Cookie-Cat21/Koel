/**
 * Signal Board browse — latest research scores from ``symbol_scores``.
 * Postgres only. Higher score ≠ buy (NFA).
 */

import type { Pool } from "pg";

import {
  MAX_STOCK_NAME_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { attachRankDeltas, sortByScoreDesc } from "@/lib/api/signal-ranks";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import {
  gateShortLabel,
  isSelectiveGate,
  normalizeForecastGate,
} from "@/lib/forecast-gate";

export const MAX_SIGNAL_REASON_LENGTH = 240;
export const MAX_SIGNAL_REASONS = 8;

/** Prefer current research model for the leaderboard. */
export const SIGNAL_BOARD_MODEL = "path_v5";

export type SignalRow = {
  symbol: string;
  name: string | null;
  score: number | null;
  as_of: string | null;
  model_version: string;
  reasons: string[];
  bar_count: number | null;
  /** True when a selective/always-on forecast exists for latest as_of. */
  spoke: boolean;
  forecast_gate: string | null;
  forecast_gate_label: string | null;
  forecast_confidence: number | null;
  forecast_confidence_band: string | null;
  /** 1-based position on the current board (1 = highest score). */
  rank: number;
  /** Position on the prior as_of board; null if new / no prior snapshot. */
  prior_rank: number | null;
  /** prior_rank − rank (+ = rose). Null when prior_rank is null. */
  rank_delta: number | null;
};

export type SignalBoardResult = {
  items: SignalRow[];
  as_of: string | null;
  prior_as_of: string | null;
  model_version: string;
};

function sanitizeReason(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const cleaned = sanitizeDisclosureText(raw, MAX_SIGNAL_REASON_LENGTH);
  return cleaned || null;
}

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

async function queryBoardAsOfDates(
  pool: Pool,
  modelVersion: string,
): Promise<{ asOf: string | null; priorAsOf: string | null }> {
  const result = await pool.query<{ as_of: Date | string }>(
    `SELECT as_of
       FROM symbol_scores
      WHERE model_version = $1
      GROUP BY as_of
      ORDER BY as_of DESC
      LIMIT 2`,
    [modelVersion],
  );
  const asOf = result.rows[0] ? asDateIso(result.rows[0].as_of) : null;
  const priorAsOf = result.rows[1] ? asDateIso(result.rows[1].as_of) : null;
  return { asOf, priorAsOf };
}

async function queryScoresForAsOf(
  pool: Pool,
  modelVersion: string,
  asOf: string,
): Promise<{ symbol: string; score: number | null }[]> {
  const result = await pool.query<{
    symbol: string;
    score: number | null;
  }>(
    `SELECT symbol, score
       FROM symbol_scores
      WHERE model_version = $1
        AND as_of = $2::date`,
    [modelVersion, asOf],
  );
  const out: { symbol: string; score: number | null }[] = [];
  for (const row of result.rows) {
    const symbol = normalizeSymbol(row.symbol);
    if (!symbol) continue;
    out.push({ symbol, score: toFiniteNumber(row.score) });
  }
  return out;
}

export async function queryLatestSignals(
  pool: Pool,
  opts: { limit: number; offset: number },
): Promise<SignalBoardResult> {
  const modelVersion = SIGNAL_BOARD_MODEL;
  const { asOf, priorAsOf } = await queryBoardAsOfDates(pool, modelVersion);

  if (!asOf) {
    return {
      items: [],
      as_of: null,
      prior_as_of: null,
      model_version: modelVersion,
    };
  }

  const result = await pool.query<{
    symbol: string;
    name: string | null;
    score: number | null;
    as_of: Date | string | null;
    model_version: string;
    reasons: string[] | null;
    bar_count: number | null;
    forecast_gate: string | null;
    forecast_confidence: number | null;
    forecast_confidence_band: string | null;
  }>(
    `
    WITH scores AS (
      SELECT
        sc.symbol,
        s.name,
        sc.score,
        sc.as_of,
        sc.model_version,
        sc.reasons,
        sc.bar_count
      FROM symbol_scores sc
      JOIN stocks s ON s.symbol = sc.symbol
      WHERE sc.model_version = $1
        AND sc.as_of = $2::date
    ),
    forecasts AS (
      SELECT DISTINCT ON (fp.symbol)
        fp.symbol,
        fp.gate AS forecast_gate,
        fp.confidence AS forecast_confidence,
        fp.confidence_band AS forecast_confidence_band
      FROM forecast_points fp
      ORDER BY
        fp.symbol ASC,
        fp.as_of DESC,
        CASE
          WHEN fp.gate IN ('gated_p90', 'hpe_p90') THEN 0
          WHEN fp.gate IN ('gated_ltr', 'gated_c55', 'gated') THEN 1
          WHEN fp.confidence_band = 'high' THEN 2
          WHEN fp.confidence_band = 'medium' THEN 3
          ELSE 4
        END,
        fp.confidence DESC NULLS LAST,
        fp.computed_at DESC
    )
    SELECT
      sc.symbol,
      sc.name,
      sc.score,
      sc.as_of,
      sc.model_version,
      sc.reasons,
      sc.bar_count,
      f.forecast_gate,
      f.forecast_confidence,
      f.forecast_confidence_band
    FROM scores sc
    LEFT JOIN forecasts f ON f.symbol = sc.symbol
    `,
    [modelVersion, asOf],
  );

  const mapped: Omit<SignalRow, "rank" | "prior_rank" | "rank_delta">[] = [];
  for (const row of result.rows) {
    const symbol = normalizeSymbol(row.symbol);
    if (!symbol) continue;
    const score = toFiniteNumber(row.score);
    const reasonsRaw = Array.isArray(row.reasons) ? row.reasons : [];
    const reasons: string[] = [];
    for (const r of reasonsRaw) {
      if (reasons.length >= MAX_SIGNAL_REASONS) break;
      const cleaned = sanitizeReason(r);
      if (cleaned) reasons.push(cleaned);
    }
    const name =
      typeof row.name === "string"
        ? sanitizeDisclosureText(row.name, MAX_STOCK_NAME_LENGTH) || null
        : null;
    const barCount = toFiniteNumber(row.bar_count);
    const forecastGate = normalizeForecastGate(row.forecast_gate);
    const forecastConfidence = toFiniteNumber(row.forecast_confidence);
    const forecastBand =
      typeof row.forecast_confidence_band === "string"
        ? row.forecast_confidence_band.trim().slice(0, 16) || null
        : null;
    mapped.push({
      symbol,
      name,
      score,
      as_of: asDateIso(row.as_of),
      model_version:
        typeof row.model_version === "string" && row.model_version.trim()
          ? row.model_version.trim().slice(0, 64)
          : modelVersion,
      reasons,
      bar_count: barCount == null ? null : Math.trunc(barCount),
      spoke: isSelectiveGate(forecastGate),
      forecast_gate: forecastGate,
      forecast_gate_label: gateShortLabel(forecastGate),
      forecast_confidence: forecastConfidence,
      forecast_confidence_band: forecastBand,
    });
  }

  const priorScores =
    priorAsOf != null
      ? await queryScoresForAsOf(pool, modelVersion, priorAsOf)
      : [];
  const deltas = attachRankDeltas(mapped, priorScores);
  const ranked: SignalRow[] = sortByScoreDesc(mapped).map((row) => {
    const d = deltas.get(row.symbol);
    return {
      ...row,
      rank: d?.rank ?? 0,
      prior_rank: d?.prior_rank ?? null,
      rank_delta: d?.rank_delta ?? null,
    };
  });

  const offset = Math.max(0, opts.offset);
  return {
    items: ranked.slice(offset, offset + opts.limit),
    as_of: asOf,
    prior_as_of: priorAsOf,
    model_version: modelVersion,
  };
}

/** Re-export for tests that want ISO helpers nearby. */
export { toIso };
