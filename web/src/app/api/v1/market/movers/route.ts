import type { NextRequest } from "next/server";

import { queryMarketBrowse } from "@/lib/api/market-browse";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 50;

/**
 * GET /api/v1/market/movers — thin top movers from the same browse query.
 * Query: direction=up|down (default up), limit (default 20, max 50).
 * Sign-filtered: up ⇒ change_pct > 0, down ⇒ change_pct < 0 (no flats/nulls).
 * Session required; CSRF not required (safe GET). Postgres only.
 * Not a screener — no sector/volume/q filters, no multi-sort UI.
 */
export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  const sp = request.nextUrl.searchParams;
  const directionParam = sp.get("direction");
  let direction: "up" | "down" = "up";
  // Fail closed — non-string searchParams mocks used to throw on .trim.
  if (typeof directionParam === "string" && directionParam.trim() !== "") {
    const directionRaw = directionParam.trim().toLowerCase();
    if (directionRaw !== "up" && directionRaw !== "down") {
      return jsonError(
        400,
        "validation_error",
        "direction must be up or down.",
      );
    }
    direction = directionRaw;
  }

  // Digits-only SafeInteger — reject float trunc / sci-notation soft-accept.
  const limitParsed = toSafePositiveInt(sp.get("limit") ?? String(DEFAULT_LIMIT));
  let limit = limitParsed == null ? DEFAULT_LIMIT : limitParsed;
  limit = Math.min(limit, MAX_LIMIT);

  const sort = direction === "down" ? "change_pct_asc" : "change_pct";

  try {
    const pool = getPool();
    const browsed = await queryMarketBrowse(pool, {
      limit,
      offset: 0,
      sort,
      direction,
    });
    // Re-assert sign after finite coerce — never label a null/flat as a mover.
    const items = browsed.filter((row) => {
      const pct = row.change_pct;
      if (pct == null || !Number.isFinite(pct)) return false;
      return direction === "down" ? pct < 0 : pct > 0;
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
