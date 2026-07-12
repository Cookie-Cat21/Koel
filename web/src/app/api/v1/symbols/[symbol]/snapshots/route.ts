import type { NextRequest } from "next/server";

import { toFiniteNumber } from "@/lib/api/market-browse";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ symbol: string }> };

/**
 * GET /api/v1/symbols/{symbol}/snapshots — ascending ts for sparkline.
 */
export async function GET(request: NextRequest, context: RouteContext) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  const { symbol: raw } = await context.params;
  const symbol = normalizeSymbol(decodeURIComponent(raw));
  if (!symbol) {
    return jsonError(400, "invalid_symbol", "Invalid symbol.");
  }

  let limit = 60;
  const limitRaw = request.nextUrl.searchParams.get("limit");
  if (limitRaw != null) {
    // Digits-only SafeInteger — Number("1e2") / precision-loss must not pass.
    const n = toSafePositiveInt(limitRaw);
    if (n == null) {
      return jsonError(400, "validation_error", "limit must be a positive integer.");
    }
    limit = Math.min(n, 200);
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

    // Fetch newest N, then reverse to ascending for chart polyline.
    const result = await pool.query<{
      ts: Date | string;
      price: number;
      change_pct: number | null;
    }>(
      `SELECT ts, price, change_pct
       FROM price_snapshots
       WHERE symbol = $1
       ORDER BY ts DESC
       LIMIT $2`,
      [symbol, limit],
    );

    // Drop non-finite prices entirely — sparkline needs ≥2 real ticks, not null stubs.
    const points = result.rows
      .flatMap((row) => {
        const price = toFiniteNumber(row.price);
        if (price == null) return [];
        return [
          {
            ts: toIso(row.ts),
            price,
            change_pct: toFiniteNumber(row.change_pct),
          },
        ];
      })
      .reverse();

    return jsonOk({ points });
  } catch (err) {
    console.error("GET /symbols/:symbol/snapshots failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
