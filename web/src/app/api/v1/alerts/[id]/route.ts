import type { NextRequest } from "next/server";

import { readJsonBody } from "@/lib/api/read-json-body";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { MAX_ISO_INPUT_LENGTH, toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSessionAndCsrf } from "@/lib/auth/guard";
import { alertOwnedByUser, cancelAlert, muteAlert } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ id: string }> };

const CTRL_RE = /[\u0000-\u001F\u007F-\u009F]/;

function parseMutedUntil(raw: unknown): { ok: true; value: string | null } | { ok: false } {
  if (raw === null) return { ok: true, value: null };
  if (typeof raw !== "string") return { ok: false };
  const trimmed = raw.trim();
  if (!trimmed || trimmed.length > MAX_ISO_INPUT_LENGTH || CTRL_RE.test(trimmed)) {
    return { ok: false };
  }
  const iso = toIso(trimmed);
  return iso ? { ok: true, value: iso } : { ok: false };
}

/**
 * PATCH /api/v1/alerts/{id} — set or clear mute until timestamp. CSRF required.
 */
export async function PATCH(request: NextRequest, context: RouteContext) {
  const gated = requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

  const { id: rawId } = await context.params;
  const ruleId = toSafePositiveInt(rawId);
  if (ruleId == null) {
    return jsonError(400, "validation_error", "Invalid alert id.");
  }

  const parsed = await readJsonBody(request);
  if (!parsed.ok) {
    if (parsed.reason === "too_large") {
      return jsonError(400, "validation_error", "Request body too large.");
    }
    return jsonError(400, "validation_error", "Invalid JSON body.");
  }
  if (typeof parsed.value !== "object" || parsed.value === null) {
    return jsonError(400, "validation_error", "Invalid request body.");
  }

  const obj = parsed.value as Record<string, unknown>;
  if (!Object.prototype.hasOwnProperty.call(obj, "muted_until")) {
    return jsonError(400, "validation_error", "muted_until is required.");
  }
  const mutedUntil = parseMutedUntil(obj.muted_until);
  if (!mutedUntil.ok) {
    return jsonError(
      400,
      "validation_error",
      "muted_until must be an ISO timestamp or null.",
    );
  }

  try {
    const rule = await muteAlert(gated.session.user_id, ruleId, mutedUntil.value);
    if (!rule) {
      return jsonError(404, "not_found", "Alert not found.");
    }
    return jsonOk(rule);
  } catch (err) {
    console.error("PATCH /alerts failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}

/**
 * DELETE /api/v1/alerts/{id} — soft cancel (active=false). CSRF required.
 * 404 when id is missing or not owned by session user.
 */
export async function DELETE(request: NextRequest, context: RouteContext) {
  const gated = requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

  const { id: rawId } = await context.params;
  // Digits-only SafeInteger via helper — reject 1e21 / precision-loss ids that
  // could cancel the wrong row (Number(oversized) used to alias).
  const ruleId = toSafePositiveInt(rawId);
  if (ruleId == null) {
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
