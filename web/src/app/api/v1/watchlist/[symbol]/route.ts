import type { NextRequest } from "next/server";

import { normalizeSymbol } from "@/lib/api/symbol";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSessionAndCsrf } from "@/lib/auth/guard";
import { unwatchSymbol } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ symbol: string }> };

/**
 * DELETE /api/v1/watchlist/{symbol} — unwatch + deactivate rules (CSRF).
 * Soft messaging: 200 with removed:false when not on watchlist.
 */
export async function DELETE(request: NextRequest, context: RouteContext) {
  const gated = requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

  const { symbol: raw } = await context.params;
  const symbol = normalizeSymbol(raw);
  if (!symbol) {
    return jsonError(400, "invalid_symbol", "Invalid CSE symbol.");
  }

  try {
    const result = await unwatchSymbol(gated.session.user_id, symbol);
    return jsonOk({
      removed: result.removed,
      deactivated_alerts: result.deactivated_alerts,
    });
  } catch (err) {
    console.error("DELETE /watchlist failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
