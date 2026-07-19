import type { NextRequest } from "next/server";

import { queryLatestSignals } from "@/lib/api/signals";
import { toNonNegativeSafeInt, toSafePositiveInt } from "@/lib/api/safe-int";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 100;

/**
 * GET /api/v1/signals — Signal Board research scores (Postgres only).
 * Sorted high→low score with prior-day rank Δ. Higher ≠ buy. Session required.
 */
export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  const sp = request.nextUrl.searchParams;
  const limitParsed = toSafePositiveInt(sp.get("limit") ?? String(DEFAULT_LIMIT));
  let limit = limitParsed == null ? DEFAULT_LIMIT : limitParsed;
  limit = Math.min(limit, MAX_LIMIT);

  const offset = toNonNegativeSafeInt(sp.get("offset") ?? "0", 0);

  try {
    const pool = getPool();
    const board = await queryLatestSignals(pool, { limit, offset });
    return jsonOk({
      items: board.items,
      as_of: board.as_of,
      prior_as_of: board.prior_as_of,
      model_version: board.model_version,
      limit,
      offset,
      disclaimer:
        "Research scores from public CSE path data — not financial advice. Higher ≠ buy.",
    });
  } catch (err) {
    console.error("GET /signals failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
