import type { NextRequest } from "next/server";

import { queryPeopleGraph } from "@/lib/api/people-graph";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const DEFAULT_LIMIT = 250;
const MAX_LIMIT = 500;

/**
 * GET /api/v1/graph/people — directors/CEOs linked to companies.
 * Sizes by linked company market cap × role weight — NOT personal net worth.
 */
export async function GET(request: NextRequest) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  const sp = request.nextUrl.searchParams;
  const limitParsed = toSafePositiveInt(sp.get("limit") ?? String(DEFAULT_LIMIT));
  let limit = limitParsed == null ? DEFAULT_LIMIT : limitParsed;
  limit = Math.min(limit, MAX_LIMIT);
  const minRaw = (sp.get("min_confidence") ?? "medium").toLowerCase();
  const minConfidence =
    minRaw === "high" || minRaw === "low" ? minRaw : "medium";
  // Default: all board roles. Pass leadership=1 to restrict to chair/CEO/MD/…
  const leadershipOnly = sp.get("leadership") === "1";

  try {
    const pool = getPool();
    const { people, edges } = await queryPeopleGraph(pool, {
      limit,
      minConfidence,
      leadershipOnly,
    });
    return jsonOk({
      people,
      edges,
      limit,
      min_confidence: minConfidence,
      disclaimer:
        "People and roles come from official CSE companyProfile boards. Influence score uses linked company market value × role weight — it is NOT personal net worth and not financial advice.",
    });
  } catch (err) {
    console.error("GET /graph/people failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
