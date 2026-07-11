import type { NextRequest } from "next/server";

import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ symbol: string }> };

/**
 * GET /api/v1/symbols/{symbol}/disclosures — recent CSE filings from Postgres.
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
    }>(
      `SELECT id, external_id, title, category, url, published_at, company_name
       FROM disclosures
       WHERE symbol = $1
       ORDER BY published_at DESC, id DESC
       LIMIT $2`,
      [symbol, limit],
    );

    const items = result.rows.map((row) => ({
      id: Number(row.id),
      external_id: row.external_id,
      title: row.title,
      category: row.category,
      url: row.url,
      published_at: toIso(row.published_at),
      company_name: row.company_name,
    }));

    return jsonOk({ items });
  } catch (err) {
    console.error("GET /symbols/:symbol/disclosures failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
