import type { NextRequest } from "next/server";

import { readJsonBody } from "@/lib/api/read-json-body";
import { toNonNegativeSafeInt } from "@/lib/api/safe-int";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession, requireSessionAndCsrf } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type PreferencesPayload = {
  digest_enabled: boolean;
  quiet_hours_start: number | null;
  quiet_hours_end: number | null;
  alert_quota_max: number;
};

function quietHourFromDb(raw: unknown): number | null {
  if (raw == null) return null;
  const n = toNonNegativeSafeInt(raw, -1);
  return n >= 0 && n <= 23 ? n : null;
}

function quietHourFromBody(raw: unknown): { ok: true; value: number | null } | { ok: false } {
  if (raw === null) return { ok: true, value: null };
  const n = toNonNegativeSafeInt(raw, -1);
  return n >= 0 && n <= 23 ? { ok: true, value: n } : { ok: false };
}

function mapPreferences(row: {
  digest_enabled: boolean;
  quiet_hours_start: string | number | null;
  quiet_hours_end: string | number | null;
  alert_quota_max: string | number;
}): PreferencesPayload | null {
  if (typeof row.digest_enabled !== "boolean") return null;
  const quota = toNonNegativeSafeInt(row.alert_quota_max, -1);
  if (quota < 0) return null;
  return {
    digest_enabled: row.digest_enabled,
    quiet_hours_start: quietHourFromDb(row.quiet_hours_start),
    quiet_hours_end: quietHourFromDb(row.quiet_hours_end),
    alert_quota_max: quota,
  };
}

async function fetchPreferences(userId: number): Promise<PreferencesPayload | null> {
  const pool = getPool();
  const result = await pool.query<{
    digest_enabled: boolean;
    quiet_hours_start: string | number | null;
    quiet_hours_end: string | number | null;
    alert_quota_max: string | number;
  }>(
    `SELECT digest_enabled, quiet_hours_start, quiet_hours_end, alert_quota_max
       FROM users
      WHERE id = $1`,
    [userId],
  );
  const row = result.rows[0];
  return row ? mapPreferences(row) : null;
}

export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  try {
    const prefs = await fetchPreferences(gated.session.user_id);
    if (!prefs) {
      return jsonError(401, "unauthorized", "Authentication required.");
    }
    return jsonOk(prefs);
  } catch (err) {
    console.error("GET /me/preferences failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}

export async function PATCH(request: NextRequest) {
  const gated = await requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

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
  if (typeof obj.digest_enabled !== "boolean") {
    return jsonError(400, "validation_error", "digest_enabled must be boolean.");
  }
  const start = quietHourFromBody(obj.quiet_hours_start);
  const end = quietHourFromBody(obj.quiet_hours_end);
  if (!start.ok || !end.ok) {
    return jsonError(
      400,
      "validation_error",
      "quiet hours must be null or an integer from 0 to 23.",
    );
  }
  if ((start.value == null) !== (end.value == null)) {
    return jsonError(
      400,
      "validation_error",
      "Set both quiet hours, or clear both.",
    );
  }

  try {
    const pool = getPool();
    const result = await pool.query<{
      digest_enabled: boolean;
      quiet_hours_start: string | number | null;
      quiet_hours_end: string | number | null;
      alert_quota_max: string | number;
    }>(
      `UPDATE users
          SET digest_enabled = $1,
              quiet_hours_start = $2,
              quiet_hours_end = $3
        WHERE id = $4
        RETURNING digest_enabled, quiet_hours_start, quiet_hours_end,
                  alert_quota_max`,
      [obj.digest_enabled, start.value, end.value, gated.session.user_id],
    );
    const row = result.rows[0];
    const prefs = row ? mapPreferences(row) : null;
    if (!prefs) {
      return jsonError(401, "unauthorized", "Authentication required.");
    }
    return jsonOk(prefs);
  } catch (err) {
    console.error("PATCH /me/preferences failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
