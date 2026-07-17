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
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import {
  gateShortLabel,
  normalizeForecastGate,
} from "@/lib/forecast-gate";

export const MAX_SIGNAL_REASON_LENGTH = 240;
export const MAX_SIGNAL_REASONS = 8;

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
};

function sanitizeReason(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const cleaned = sanitizeDisclosureText(raw, MAX_SIGNAL_REASON_LENGTH);
  return cleaned || null;
}

export async function queryLatestSignals(
  pool: Pool,
  opts: { limit: number; offset: number },
): Promise<SignalRow[]> {
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
      SELECT DISTINCT ON (sc.symbol)
        sc.symbol,
        s.name,
        sc.score,
        sc.as_of,
        sc.model_version,
        sc.reasons,
        sc.bar_count
      FROM symbol_scores sc
      JOIN stocks s ON s.symbol = sc.symbol
      ORDER BY sc.symbol ASC, sc.as_of DESC, sc.computed_at DESC
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
          WHEN fp.gate IN ('gated_c55', 'gated') THEN 1
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
  );

  // Sort by score in app after DISTINCT ON (PG can't ORDER BY score with DISTINCT ON symbol).
  const mapped: SignalRow[] = [];
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
    let asOf: string | null = null;
    if (row.as_of instanceof Date) {
      asOf = row.as_of.toISOString().slice(0, 10);
    } else if (typeof row.as_of === "string") {
      asOf = row.as_of.slice(0, 10);
    }
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
      as_of: asOf,
      model_version:
        typeof row.model_version === "string" && row.model_version.trim()
          ? row.model_version.trim().slice(0, 64)
          : "unknown",
      reasons,
      bar_count: barCount == null ? null : Math.trunc(barCount),
      spoke: forecastGate != null || forecastConfidence != null,
      forecast_gate: forecastGate,
      forecast_gate_label: gateShortLabel(forecastGate),
      forecast_confidence: forecastConfidence,
      forecast_confidence_band: forecastBand,
    });
  }

  mapped.sort((a, b) => {
    const sa = a.score ?? Number.NEGATIVE_INFINITY;
    const sb = b.score ?? Number.NEGATIVE_INFINITY;
    if (sb !== sa) return sb - sa;
    return a.symbol.localeCompare(b.symbol);
  });

  const offset = Math.max(0, opts.offset);
  return mapped.slice(offset, offset + opts.limit);
}

/** Re-export for tests that want ISO helpers nearby. */
export { toIso };
