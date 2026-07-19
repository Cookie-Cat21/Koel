import type { NextRequest } from "next/server";

import {
  DEFAULT_DAILY_BARS_LIMIT,
  MAX_DAILY_BARS_LIMIT,
  normalizeDailyBar,
} from "@/lib/api/daily-bars";
import { normalizeIndexCodeParam } from "@/lib/api/indexes";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ code: string }> };

/**
 * GET /api/v1/indexes/{code}/daily-bars — ASPI / S&P SL20 daily path.
 * Postgres ``daily_bars`` only (index close series from CSE). Session required.
 */
export async function GET(request: NextRequest, context: RouteContext) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  const { code: raw } = await context.params;
  const code = normalizeIndexCodeParam(raw);
  if (!code) {
    return jsonError(400, "invalid_index", "Unknown index code.");
  }

  let limit = DEFAULT_DAILY_BARS_LIMIT;
  const limitRaw = request.nextUrl.searchParams.get("limit");
  if (limitRaw != null) {
    const n = toSafePositiveInt(limitRaw);
    if (n == null) {
      return jsonError(
        400,
        "validation_error",
        "limit must be a positive integer.",
      );
    }
    limit = Math.min(n, MAX_DAILY_BARS_LIMIT);
  }

  try {
    const pool = getPool();
    const result = await pool.query<{
      trade_date: Date | string;
      open: number | null;
      high: number | null;
      low: number | null;
      price: number;
      volume: number | null;
    }>(
      `
      SELECT trade_date, open, high, low, price, volume
      FROM daily_bars
      WHERE symbol = $1
      ORDER BY trade_date DESC
      LIMIT $2
      `,
      [code, limit],
    );

    const bars = result.rows
      .map((row) => normalizeDailyBar(row))
      .filter((b): b is NonNullable<typeof b> => b != null)
      .reverse();

    return jsonOk({
      code,
      count: bars.length,
      bars,
      disclaimer:
        "Index daily path from koel (CSE index closes) — research only, not financial advice.",
    });
  } catch (err) {
    console.error("GET /indexes/:code/daily-bars failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
