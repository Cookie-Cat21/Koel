import type { NextRequest } from "next/server";

import {
  normalizeConfidence,
  queryCompanyGraph,
  type GraphConfidence,
} from "@/lib/api/graph";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { normalizeSymbol } from "@/lib/api/symbol";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const DEFAULT_LIMIT = 80;
const MAX_LIMIT = 200;

/**
 * GET /api/v1/graph — company ownership / equity research graph (Postgres only).
 */
export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  const sp = request.nextUrl.searchParams;
  const limitParsed = toSafePositiveInt(sp.get("limit") ?? String(DEFAULT_LIMIT));
  let limit = limitParsed == null ? DEFAULT_LIMIT : limitParsed;
  limit = Math.min(limit, MAX_LIMIT);

  const minRaw = sp.get("min_confidence") ?? "medium";
  const minConfidence: GraphConfidence =
    normalizeConfidence(minRaw) ?? "medium";
  const focus = normalizeSymbol(sp.get("symbol"));
  const includeIsolates = sp.get("include_isolates") === "1";

  try {
    const pool = getPool();
    const { nodes, edges } = await queryCompanyGraph(pool, {
      minConfidence,
      limit,
      focusSymbol: focus,
      includeIsolates,
    });
    return jsonOk({
      nodes,
      edges,
      limit,
      min_confidence: minConfidence,
      focus_symbol: focus,
      disclaimer:
        "Research graph from public CSE filings — not financial advice. Relationships and equity figures may be incomplete or wrong; verify in the source PDF.",
    });
  } catch (err) {
    console.error("GET /graph failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
