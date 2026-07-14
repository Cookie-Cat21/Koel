import type { NextRequest } from "next/server";

import { CSRF_COOKIE, SESSION_COOKIE } from "@/lib/auth/config";
import { jsonOk, jsonError } from "@/lib/auth/errors";
import { requireSessionAndCsrf } from "@/lib/auth/guard";
import { clearAuthCookieOptions } from "@/lib/auth/session";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/**
 * POST /api/v1/auth/logout-all — revoke all dash_sessions for the user and
 * clear this browser's cookies (A2). Other devices lose access on next
 * session check against dash_sessions when wired; until then TTL still bounds.
 */
export async function POST(request: NextRequest) {
  const gated = requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

  try {
    const pool = getPool();
    await pool.query(
      `UPDATE dash_sessions
          SET revoked_at = now()
        WHERE user_id = $1
          AND revoked_at IS NULL`,
      [gated.session.user_id],
    );
  } catch (err) {
    console.error("POST /auth/logout-all failed", err);
    return jsonError(503, "degraded", "Could not revoke sessions.");
  }

  const res = jsonOk({ ok: true, revoked: true });
  res.cookies.set(SESSION_COOKIE, "", clearAuthCookieOptions(true));
  res.cookies.set(CSRF_COOKIE, "", clearAuthCookieOptions(false));
  return res;
}
