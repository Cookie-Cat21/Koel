import type { NextRequest } from "next/server";

import {
  MAX_BRIEF_LENGTH,
  MAX_DISCLOSURE_TITLE_LENGTH,
  sanitizeBriefText,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { toNonNegativeSafeInt, toSafePositiveInt } from "@/lib/api/safe-int";
import { normalizeSymbolParam } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ symbol: string }> };

const MAX_METRIC_ITEMS = 8;
const MAX_METRIC_TEXT = 32;

const METRIC_KINDS = new Set(["quarterly", "annual", "unknown"]);
const METRIC_ENTITIES = new Set(["group", "company", "unknown"]);
const METRIC_SCALES = new Set(["units", "thousands", "millions", "unknown"]);
const MATCH_QUALITIES = new Set([
  "exact_yoy",
  "approx_yoy",
  "missing_prior",
  "scale_mismatch",
  "entity_mismatch",
  "currency_mismatch",
  "skipped",
]);

function allowlistedText(raw: unknown, allowed: ReadonlySet<string>): string | null {
  const text = sanitizeDisclosureText(
    typeof raw === "string" ? raw : null,
    MAX_METRIC_TEXT,
  );
  return text && allowed.has(text) ? text : null;
}

function metricCurrency(raw: unknown): string {
  const text = sanitizeDisclosureText(
    typeof raw === "string" ? raw : null,
    MAX_METRIC_TEXT,
  );
  return text && /^[A-Z]{3,8}$/.test(text) ? text : "LKR";
}

function dateOnly(raw: unknown): string | null {
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
  }
  const iso = toIso(raw);
  return iso ? iso.slice(0, 10) : null;
}

/**
 * GET /api/v1/symbols/{symbol}/metrics — recent filing metrics + YoY compare.
 * Postgres only; no upstream CSE calls from web.
 */
export async function GET(request: NextRequest, context: RouteContext) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  const { symbol: raw } = await context.params;
  const symbol = normalizeSymbolParam(raw);
  if (!symbol) {
    return jsonError(400, "invalid_symbol", "Invalid symbol.");
  }

  try {
    const pool = getPool();
    const exists = await pool.query(
      `SELECT 1 FROM stocks WHERE symbol = $1`,
      [symbol],
    );
    if (exists.rows.length === 0) {
      return jsonError(404, "not_found", "Unknown symbol.");
    }

    const metrics = await pool.query<{
      id: string | number;
      kind: string;
      fiscal_period_end: Date | string | null;
      entity: string;
      scale: string;
      currency: string;
      revenue: number | string | null;
      profit: number | string | null;
      eps_basic: number | string | null;
      extract_ok: boolean;
      match_quality: string | null;
      eps_delta_pct: number | string | null;
      revenue_delta_pct: number | string | null;
      profit_delta_pct: number | string | null;
      prior_filing_metrics_id: string | number | null;
    }>(
      `SELECT fm.id, fm.kind, fm.fiscal_period_end, fm.entity, fm.scale,
              fm.currency, fm.revenue, fm.profit, fm.eps_basic, fm.extract_ok,
              fc.match_quality, fc.eps_delta_pct, fc.revenue_delta_pct,
              fc.profit_delta_pct, fc.prior_filing_metrics_id
         FROM filing_metrics fm
         LEFT JOIN filing_comparisons fc ON fc.filing_metrics_id = fm.id
        WHERE fm.symbol = $1
        ORDER BY fm.fiscal_period_end DESC NULLS LAST, fm.id DESC
        LIMIT $2`,
      [symbol, MAX_METRIC_ITEMS],
    );

    const items = metrics.rows.flatMap((row) => {
      const id = toSafePositiveInt(row.id);
      if (id == null) return [];
      const kind = allowlistedText(row.kind, METRIC_KINDS);
      const entity = allowlistedText(row.entity, METRIC_ENTITIES);
      const scale = allowlistedText(row.scale, METRIC_SCALES);
      if (!kind || !entity || !scale) return [];

      const matchQuality = allowlistedText(row.match_quality, MATCH_QUALITIES);
      const priorId =
        row.prior_filing_metrics_id == null
          ? null
          : toSafePositiveInt(row.prior_filing_metrics_id);
      const comparison =
        matchQuality == null
          ? null
          : {
              match_quality: matchQuality,
              eps_delta_pct: toFiniteNumber(row.eps_delta_pct),
              revenue_delta_pct: toFiniteNumber(row.revenue_delta_pct),
              profit_delta_pct: toFiniteNumber(row.profit_delta_pct),
              prior_filing_metrics_id: priorId,
            };

      return [
        {
          id,
          kind,
          fiscal_period_end: dateOnly(row.fiscal_period_end),
          entity,
          scale,
          currency: metricCurrency(row.currency),
          revenue: toFiniteNumber(row.revenue),
          profit: toFiniteNumber(row.profit),
          eps_basic: toFiniteNumber(row.eps_basic),
          extract_ok: row.extract_ok === true,
          comparison,
        },
      ];
    });

    const briefResult = await pool.query<{
      title: string;
      brief: string | null;
      published_at: Date | string;
    }>(
      `SELECT d.title, b.brief, d.published_at
         FROM disclosure_briefs b
         JOIN disclosures d ON d.id = b.disclosure_id
        WHERE d.symbol = $1 AND b.status = 'ready'
        ORDER BY
          CASE
            WHEN d.external_id LIKE 'fin-%' THEN 0
            WHEN d.title ILIKE '%financial%' OR d.title ILIKE '%interim%'
              OR d.category ILIKE '%financial%' THEN 1
            ELSE 2
          END,
          d.published_at DESC NULLS LAST,
          d.id DESC
        LIMIT 1`,
      [symbol],
    );
    const briefRow = briefResult.rows[0];
    const briefText = sanitizeBriefText(briefRow?.brief ?? null, "ready");
    const briefTitle = sanitizeDisclosureText(
      briefRow?.title,
      MAX_DISCLOSURE_TITLE_LENGTH,
    );
    const briefPublishedAt = toIso(briefRow?.published_at);
    const brief =
      briefText && briefTitle && briefPublishedAt
        ? {
            title: briefTitle,
            text: sanitizeDisclosureText(briefText, MAX_BRIEF_LENGTH) ?? briefText,
            published_at: briefPublishedAt,
          }
        : null;

    // Coverage counters for user-facing data-quality notices (Postgres only).
    const [metricsQuality, disclosureQuality] = await Promise.all([
      pool.query<{
        metrics_attempted: number | string;
        metrics_ok: number | string;
        metrics_failed: number | string;
      }>(
        `SELECT COUNT(*)::int AS metrics_attempted,
                COUNT(*) FILTER (WHERE extract_ok)::int AS metrics_ok,
                COUNT(*) FILTER (WHERE NOT extract_ok)::int AS metrics_failed
           FROM filing_metrics
          WHERE symbol = $1`,
        [symbol],
      ),
      pool.query<{
        disclosures: number | string;
        with_pdf: number | string;
        financial_filings: number | string;
        briefs_ready: number | string;
        briefs_pending: number | string;
        briefs_failed: number | string;
      }>(
        `SELECT COUNT(*)::int AS disclosures,
                COUNT(*) FILTER (WHERE d.pdf_url IS NOT NULL)::int AS with_pdf,
                COUNT(*) FILTER (
                  WHERE d.external_id LIKE 'fin-%'
                     OR d.title ILIKE '%financial%'
                     OR d.title ILIKE '%interim%'
                     OR d.category ILIKE '%financial%'
                )::int AS financial_filings,
                COUNT(*) FILTER (WHERE b.status = 'ready')::int AS briefs_ready,
                COUNT(*) FILTER (
                  WHERE b.status IN ('pending', 'processing')
                )::int AS briefs_pending,
                COUNT(*) FILTER (WHERE b.status = 'failed')::int AS briefs_failed
           FROM disclosures d
           LEFT JOIN disclosure_briefs b ON b.disclosure_id = d.id
          WHERE d.symbol = $1`,
        [symbol],
      ),
    ]);

    const mq = metricsQuality.rows[0];
    const dq = disclosureQuality.rows[0];
    const quality = {
      metrics_attempted: toNonNegativeSafeInt(mq?.metrics_attempted),
      metrics_ok: toNonNegativeSafeInt(mq?.metrics_ok),
      metrics_failed: toNonNegativeSafeInt(mq?.metrics_failed),
      disclosures: toNonNegativeSafeInt(dq?.disclosures),
      with_pdf: toNonNegativeSafeInt(dq?.with_pdf),
      financial_filings: toNonNegativeSafeInt(dq?.financial_filings),
      briefs_ready: toNonNegativeSafeInt(dq?.briefs_ready),
      briefs_pending: toNonNegativeSafeInt(dq?.briefs_pending),
      briefs_failed: toNonNegativeSafeInt(dq?.briefs_failed),
    };

    return jsonOk({ items, brief, quality });
  } catch (err) {
    console.error("GET /symbols/:symbol/metrics failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
