import type { NextRequest } from "next/server";
import { randomBytes } from "node:crypto";

import {
  normalizeFilingTags,
  type FilingCategoryTag,
} from "@/lib/api/filing-categories";
import { readJsonBody } from "@/lib/api/read-json-body";
import { toNonNegativeSafeInt } from "@/lib/api/safe-int";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession, requireSessionAndCsrf } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

export type PreferencesPayload = {
  digest_enabled: boolean;
  quiet_hours_start: number | null;
  quiet_hours_end: number | null;
  alert_quota_max: number;
  watchlist_auto_move_pct: number | null;
  disclosure_category_prefs: FilingCategoryTag[];
  tv_webhook_token: string | null;
};

function quietHourFromDb(raw: unknown): number | null {
  if (raw == null) return null;
  const n = toNonNegativeSafeInt(raw, -1);
  return n >= 0 && n <= 23 ? n : null;
}

function quietHourFromBody(
  raw: unknown,
): { ok: true; value: number | null } | { ok: false } {
  if (raw === null) return { ok: true, value: null };
  const n = toNonNegativeSafeInt(raw, -1);
  return n >= 0 && n <= 23 ? { ok: true, value: n } : { ok: false };
}

function autoMoveFromDb(raw: unknown): number | null {
  if (raw == null) return null;
  if (typeof raw === "boolean") return null;
  const n = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isFinite(n) || n <= 0 || n > 50) return null;
  return n;
}

function mapPreferences(row: {
  digest_enabled: boolean;
  quiet_hours_start: string | number | null;
  quiet_hours_end: string | number | null;
  alert_quota_max: string | number;
  watchlist_auto_move_pct: string | number | null;
  disclosure_category_prefs: string[] | null;
  tv_webhook_token: string | null;
}): PreferencesPayload | null {
  if (typeof row.digest_enabled !== "boolean") return null;
  const quota = toNonNegativeSafeInt(row.alert_quota_max, -1);
  if (quota < 0) return null;
  const token =
    typeof row.tv_webhook_token === "string" && row.tv_webhook_token.trim()
      ? row.tv_webhook_token.trim()
      : null;
  return {
    digest_enabled: row.digest_enabled,
    quiet_hours_start: quietHourFromDb(row.quiet_hours_start),
    quiet_hours_end: quietHourFromDb(row.quiet_hours_end),
    alert_quota_max: quota,
    watchlist_auto_move_pct: autoMoveFromDb(row.watchlist_auto_move_pct),
    disclosure_category_prefs: normalizeFilingTags(
      row.disclosure_category_prefs,
    ),
    tv_webhook_token: token,
  };
}

async function fetchPreferences(
  userId: number,
): Promise<PreferencesPayload | null> {
  const pool = getPool();
  const result = await pool.query<{
    digest_enabled: boolean;
    quiet_hours_start: string | number | null;
    quiet_hours_end: string | number | null;
    alert_quota_max: string | number;
    watchlist_auto_move_pct: string | number | null;
    disclosure_category_prefs: string[] | null;
    tv_webhook_token: string | null;
  }>(
    `SELECT digest_enabled, quiet_hours_start, quiet_hours_end, alert_quota_max,
            watchlist_auto_move_pct, disclosure_category_prefs, tv_webhook_token
       FROM users
      WHERE id = $1`,
    [userId],
  );
  const row = result.rows[0];
  return row ? mapPreferences(row) : null;
}

async function syncAutoMoveRules(
  userId: number,
  pct: number | null,
): Promise<void> {
  const pool = getPool();
  if (pct == null) {
    await pool.query(
      `UPDATE alert_rules
          SET active = FALSE
        WHERE user_id = $1
          AND type = 'daily_move'
          AND active IS TRUE
          AND threshold IN (3, 5, 10)`,
      [userId],
    );
    return;
  }
  const watches = await pool.query<{ symbol: string }>(
    `SELECT symbol FROM watchlist_items WHERE user_id = $1`,
    [userId],
  );
  for (const { symbol } of watches.rows) {
    const existing = await pool.query(
      `SELECT id FROM alert_rules
        WHERE user_id = $1 AND symbol = $2 AND type = 'daily_move'
          AND threshold = $3 AND active IS TRUE
        LIMIT 1`,
      [userId, symbol, pct],
    );
    if (existing.rows[0]) continue;
    await pool.query(
      `INSERT INTO alert_rules (user_id, symbol, type, threshold, active, armed)
       VALUES ($1, $2, 'daily_move', $3, TRUE, TRUE)`,
      [userId, symbol, pct],
    );
  }
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

  let autoPct: number | null | undefined = undefined;
  if ("watchlist_auto_move_pct" in obj) {
    if (obj.watchlist_auto_move_pct === null) {
      autoPct = null;
    } else if (
      typeof obj.watchlist_auto_move_pct === "number" &&
      Number.isFinite(obj.watchlist_auto_move_pct) &&
      obj.watchlist_auto_move_pct > 0 &&
      obj.watchlist_auto_move_pct <= 50
    ) {
      autoPct = obj.watchlist_auto_move_pct;
    } else {
      return jsonError(
        400,
        "validation_error",
        "watchlist_auto_move_pct must be null or a number from 0–50.",
      );
    }
  }

  if (!("disclosure_category_prefs" in obj)) {
    return jsonError(
      400,
      "validation_error",
      "disclosure_category_prefs is required.",
    );
  }
  const categoryPrefs = normalizeFilingTags(obj.disclosure_category_prefs);
  const rotateToken = obj.rotate_tv_webhook_token === true;
  const clearToken = obj.clear_tv_webhook_token === true;

  try {
    const pool = getPool();
    const sets = [
      "digest_enabled = $1",
      "quiet_hours_start = $2",
      "quiet_hours_end = $3",
      "disclosure_category_prefs = $4",
    ];
    const params: unknown[] = [
      obj.digest_enabled,
      start.value,
      end.value,
      categoryPrefs,
    ];

    if (autoPct !== undefined) {
      params.push(autoPct);
      sets.push(`watchlist_auto_move_pct = $${params.length}`);
    }
    if (clearToken) {
      sets.push("tv_webhook_token = NULL");
    } else if (rotateToken) {
      params.push(randomBytes(18).toString("base64url"));
      sets.push(`tv_webhook_token = $${params.length}`);
    }

    params.push(gated.session.user_id);
    await pool.query(
      `UPDATE users SET ${sets.join(", ")} WHERE id = $${params.length}`,
      params,
    );

    if (autoPct !== undefined) {
      await syncAutoMoveRules(gated.session.user_id, autoPct);
    }

    const prefs = await fetchPreferences(gated.session.user_id);
    if (!prefs) {
      return jsonError(401, "unauthorized", "Authentication required.");
    }
    return jsonOk(prefs);
  } catch (err) {
    console.error("PATCH /me/preferences failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
