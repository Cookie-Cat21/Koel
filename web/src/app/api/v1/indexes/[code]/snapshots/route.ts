import type { NextRequest } from "next/server";

import { normalizeIndexCodeParam } from "@/lib/api/indexes";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ code: string }> };

const DEFAULT_LIMIT = 240;
const MAX_LIMIT = 400;

/**
 * GET /api/v1/indexes/{code}/snapshots — recent index ticks for 1D expand.
 * Postgres ``index_snapshots`` only. Session required.
 */
export async function GET(request: NextRequest, context: RouteContext) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  const { code: raw } = await context.params;
  const code = normalizeIndexCodeParam(raw);
  if (!code) {
    return jsonError(400, "invalid_index", "Unknown index code.");
  }

  let limit = DEFAULT_LIMIT;
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
    limit = Math.min(n, MAX_LIMIT);
  }

  try {
    const pool = getPool();
    const result = await pool.query<{
      value: number | string | null;
      change_pct: number | string | null;
      ts: Date | string;
    }>(
      `
      SELECT value, change_pct, ts
      FROM index_snapshots
      WHERE code = $1
      ORDER BY ts DESC
      LIMIT $2
      `,
      [code, limit],
    );

    const points = result.rows
      .map((row) => {
        const price = toFiniteNumber(row.value);
        if (price == null || price <= 0) return null;
        return {
          ts: toIso(row.ts),
          price,
          change_pct: toFiniteNumber(row.change_pct),
        };
      })
      .filter((p): p is NonNullable<typeof p> => p != null)
      .reverse();

    return jsonOk({
      code,
      count: points.length,
      points,
      disclaimer:
        "Index ticks from Chime poller — research only, not financial advice.",
    });
  } catch (err) {
    console.error("GET /indexes/:code/snapshots failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
