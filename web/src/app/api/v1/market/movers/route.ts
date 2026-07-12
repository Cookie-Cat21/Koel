import type { NextRequest } from "next/server";

import { queryMarketBrowse } from "@/lib/api/market-browse";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 50;

/**
 * GET /api/v1/market/movers — thin top movers from the same browse query.
 * Query: direction=up|down (default up), limit (default 20, max 50).
 * Session required; CSRF not required (safe GET). Postgres only.
 * Not a screener — no sector/volume/q filters, no multi-sort UI.
 */
export async function GET(request: NextRequest) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  const sp = request.nextUrl.searchParams;
  const directionRaw = (sp.get("direction") ?? "up").trim().toLowerCase();
  const direction = directionRaw === "down" ? "down" : "up";

  let limit = Number.parseInt(sp.get("limit") ?? String(DEFAULT_LIMIT), 10);
  if (!Number.isFinite(limit) || limit < 1) limit = DEFAULT_LIMIT;
  limit = Math.min(limit, MAX_LIMIT);

  const sort = direction === "down" ? "change_pct_asc" : "change_pct";

  try {
    const pool = getPool();
    const items = await queryMarketBrowse(pool, {
      limit,
      offset: 0,
      sort,
    });

    return jsonOk({
      items,
      direction,
      limit,
    });
  } catch (err) {
    console.error("GET /market/movers failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
