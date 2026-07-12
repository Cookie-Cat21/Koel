import type { NextRequest } from "next/server";

import { queryMarketBrowse } from "@/lib/api/market-browse";
import {
  MAX_SYMBOLS_OFFSET,
  normalizeMarketQuery,
} from "@/lib/api/market-query";
import { toNonNegativeSafeInt, toSafePositiveInt } from "@/lib/api/safe-int";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 200;

/**
 * GET /api/v1/symbols — thin market browse from Postgres (latest snapshots).
 * Query: limit (default 50, max 200), offset (max 10000), q (symbol/name
 * substring, max 64, LIKE-metachar escaped), sort=change_pct|symbol
 * (default change_pct). Session required; CSRF not required (safe GET).
 * No cse.lk. Not a screener (no sector/volume filters).
 */
export async function GET(request: NextRequest) {
  // Session only — GET must not require CSRF (double-submit is for mutations).
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  const sp = request.nextUrl.searchParams;
  // Digits-only SafeInteger — reject float trunc / sci-notation soft-accept.
  const limitParsed = toSafePositiveInt(sp.get("limit") ?? String(DEFAULT_LIMIT));
  let limit = limitParsed == null ? DEFAULT_LIMIT : limitParsed;
  limit = Math.min(limit, MAX_LIMIT);
  const offsetParsed = toNonNegativeSafeInt(sp.get("offset") ?? "0", -1);
  let offset = offsetParsed < 0 ? 0 : offsetParsed;
  offset = Math.min(offset, MAX_SYMBOLS_OFFSET);

  const q = normalizeMarketQuery(sp.get("q"));
  const sortRaw = (sp.get("sort") ?? "change_pct").trim().toLowerCase();
  const sort = sortRaw === "symbol" ? "symbol" : "change_pct";

  try {
    const pool = getPool();
    const items = await queryMarketBrowse(pool, {
      limit,
      offset,
      q: q || undefined,
      sort,
    });

    return jsonOk({
      items,
      limit,
      offset,
      sort,
      q: q || null,
    });
  } catch (err) {
    console.error("GET /symbols failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
