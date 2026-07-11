import type { NextRequest } from "next/server";

import { toIso } from "@/lib/api/time";
import { CSRF_COOKIE } from "@/lib/auth/config";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { mintCsrfToken, csrfCookieOptions } from "@/lib/auth/session";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/**
 * GET /api/v1/me — current user from session; re-issues CSRF material.
 */
export async function GET(request: NextRequest) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  try {
    const pool = getPool();
    const result = await pool.query<{
      id: string | number;
      telegram_id: string | number;
      created_at: Date | string;
    }>(
      `SELECT id, telegram_id, created_at FROM users WHERE id = $1`,
      [gated.session.user_id],
    );
    const row = result.rows[0];
    if (!row) {
      return jsonError(401, "unauthorized", "Authentication required.");
    }

    const csrf = mintCsrfToken();
    const res = jsonOk({
      id: Number(row.id),
      telegram_id: Number(row.telegram_id),
      created_at: toIso(row.created_at),
      csrf_token: csrf,
    });
    res.cookies.set(CSRF_COOKIE, csrf, csrfCookieOptions());
    return res;
  } catch (err) {
    console.error("GET /me failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
