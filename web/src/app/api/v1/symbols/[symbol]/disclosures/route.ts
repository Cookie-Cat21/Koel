import type { NextRequest } from "next/server";

import {
  MAX_DISCLOSURE_CATEGORY_LENGTH,
  MAX_DISCLOSURE_COMPANY_LENGTH,
  MAX_DISCLOSURE_EXTERNAL_ID_LENGTH,
  MAX_DISCLOSURE_TITLE_LENGTH,
  normalizeBriefStatus,
  safeAnnouncementUrl,
  safePdfUrl,
  sanitizeBriefText,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { normalizeSymbolParam } from "@/lib/api/symbol";
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
  // safeDecode — malformed % sequences must 400, not URIError 500.
  const symbol = normalizeSymbolParam(raw);
  if (!symbol) {
    return jsonError(400, "invalid_symbol", "Invalid symbol.");
  }

  let limit = 20;
  const limitRaw = request.nextUrl.searchParams.get("limit");
  if (limitRaw != null) {
    // Digits-only SafeInteger — Number("1e2") / precision-loss must not pass.
    const n = toSafePositiveInt(limitRaw);
    if (n == null) {
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
      const id = toSafePositiveInt(row.id);
      // Drop non-safe ids — Number(oversized) precision-loss aliases rows.
      if (id == null) return [];
      const brief_status = normalizeBriefStatus(row.brief_status);
      // Title/category/company/external_id: strip controls + cap (hostile DB
      // text must not balloon JSON or leak C0 into the dash).
      const title =
        sanitizeDisclosureText(row.title, MAX_DISCLOSURE_TITLE_LENGTH) ?? "";
      return [
        {
          id,
          external_id:
            sanitizeDisclosureText(
              row.external_id,
              MAX_DISCLOSURE_EXTERNAL_ID_LENGTH,
            ) ?? "",
          title,
          category: sanitizeDisclosureText(
            row.category,
            MAX_DISCLOSURE_CATEGORY_LENGTH,
          ),
          url: safeAnnouncementUrl(row.url),
          published_at: toIso(row.published_at),
          company_name: sanitizeDisclosureText(
            row.company_name,
            MAX_DISCLOSURE_COMPANY_LENGTH,
          ),
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
