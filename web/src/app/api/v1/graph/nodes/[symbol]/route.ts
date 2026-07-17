import type { NextRequest } from "next/server";

import { queryGraphNodeDetail } from "@/lib/api/graph";
import { normalizeSymbol } from "@/lib/api/symbol";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type Ctx = { params: Promise<{ symbol: string }> };

/**
 * GET /api/v1/graph/nodes/[symbol] — ego-network + equity evidence for one issuer.
 */
export async function GET(request: NextRequest, ctx: Ctx) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  const { symbol: raw } = await ctx.params;
  const symbol = normalizeSymbol(raw);
  if (!symbol) {
    return jsonError(400, "bad_symbol", "Invalid symbol.");
  }

  try {
    const pool = getPool();
    const detail = await queryGraphNodeDetail(pool, symbol);
    if (!detail) {
      return jsonError(404, "not_found", "No graph node for this symbol yet.");
    }
    return jsonOk({
      ...detail,
      disclaimer:
        "Research graph from public CSE filings — not financial advice. Not a recommendation to buy or sell.",
    });
  } catch (err) {
    console.error("GET /graph/nodes failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
