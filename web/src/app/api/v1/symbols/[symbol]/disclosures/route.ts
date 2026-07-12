import type { NextRequest } from "next/server";

import {
  normalizeBriefStatus,
  safeAnnouncementUrl,
  safePdfUrl,
  sanitizeBriefText,
} from "@/lib/api/disclosure-safe";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ symbol: string }> };

/**
 * GET /api/v1/symbols/{symbol}/disclosures — recent filings from Postgres.
 * LEFT JOIN disclosure_briefs for brief / brief_status when present.
 * pdf_url comes from disclosures (enricher); never fetches upstream from web.
 * Egress: allowlist pdf_url/url; expose brief only when brief_status=ready.
 */
export async function GET(request: NextRequest, context: RouteContext) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  const { symbol: raw } = await context.params;
  const symbol = normalizeSymbol(decodeURIComponent(raw));
  if (!symbol) {
    return jsonError(400, "invalid_symbol", "Invalid symbol.");
  }

  let limit = 20;
  const limitRaw = request.nextUrl.searchParams.get("limit");
  if (limitRaw != null) {
    const n = Number(limitRaw);
    if (!Number.isSafeInteger(n) || n < 1) {
      return jsonError(400, "validation_error", "limit must be a positive integer.");
    }
    limit = Math.min(n, 100);
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

    const result = await pool.query<{
      id: string | number;
      external_id: string;
      title: string;
      category: string | null;
      url: string;
      published_at: Date | string;
      company_name: string | null;
      pdf_url: string | null;
      brief: string | null;
      brief_status: string | null;
    }>(
      `SELECT d.id, d.external_id, d.title, d.category, d.url, d.published_at,
              d.company_name, d.pdf_url,
              b.brief, b.status AS brief_status
       FROM disclosures d
       LEFT JOIN disclosure_briefs b ON b.disclosure_id = d.id
       WHERE d.symbol = $1
       ORDER BY d.published_at DESC, d.id DESC
       LIMIT $2`,
      [symbol, limit],
    );

    const items = result.rows.flatMap((row) => {
      const id = Number(row.id);
      // Drop non-finite ids — JSON.stringify(NaN) becomes null.
      if (!Number.isFinite(id)) return [];
      const brief_status = normalizeBriefStatus(row.brief_status);
      return [
        {
          id,
          external_id: row.external_id,
          title: row.title,
          category: row.category,
          url: safeAnnouncementUrl(row.url),
          published_at: toIso(row.published_at),
          company_name: row.company_name,
          pdf_url: safePdfUrl(row.pdf_url),
          brief: sanitizeBriefText(row.brief, brief_status),
          brief_status,
        },
      ];
    });

    return jsonOk({ items });
  } catch (err) {
    console.error("GET /symbols/:symbol/disclosures failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
