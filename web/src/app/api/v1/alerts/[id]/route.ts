import type { NextRequest } from "next/server";

import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSessionAndCsrf } from "@/lib/auth/guard";
import { alertOwnedByUser, cancelAlert } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ id: string }> };

/**
 * DELETE /api/v1/alerts/{id} — soft cancel (active=false). CSRF required.
 * 404 when id is missing or not owned by session user.
 */
export async function DELETE(request: NextRequest, context: RouteContext) {
  const gated = requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

  const { id: rawId } = await context.params;
  // Digits-only + SafeInteger: reject 1e21 / precision-loss ids that could
  // cancel the wrong row (Number.isInteger alone accepts unsafe ints).
  if (!/^\d{1,15}$/.test(rawId)) {
    return jsonError(400, "validation_error", "Invalid alert id.");
  }
  const ruleId = Number(rawId);
  if (!Number.isSafeInteger(ruleId) || ruleId <= 0) {
    return jsonError(400, "validation_error", "Invalid alert id.");
  }

  try {
    const owned = await alertOwnedByUser(gated.session.user_id, ruleId);
    if (!owned) {
      return jsonError(404, "not_found", "Alert not found.");
    }

    const cancelled = await cancelAlert(gated.session.user_id, ruleId);
    return jsonOk({ cancelled });
  } catch (err) {
    console.error("DELETE /alerts failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
