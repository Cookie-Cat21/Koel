import type { NextRequest } from "next/server";

import { toIso } from "@/lib/api/time";
import { CSRF_COOKIE } from "@/lib/auth/config";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { mintCsrfToken, csrfCookieOptions } from "@/lib/auth/session";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

function toSafeId(raw: unknown): number | null {
  const n = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isSafeInteger(n) || n <= 0) return null;
  return n;
}

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

    const id = toSafeId(row.id);
    const telegram_id = toSafeId(row.telegram_id);
    // Fail closed: non-finite / unsafe ids would JSON as null and break clients.
    if (id == null || telegram_id == null) {
      return jsonError(503, "degraded", "Database unavailable.");
    }

    const csrf = mintCsrfToken();
    const res = jsonOk({
      id,
      telegram_id,
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
