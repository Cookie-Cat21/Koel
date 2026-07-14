import type { NextRequest } from "next/server";

import { toIso } from "@/lib/api/time";
import { jsonOk, jsonError } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const MAX_SESSIONS = 50;

/**
 * GET /api/v1/auth/sessions — list dash sessions for the signed-in user (A2).
 */
export async function GET(request: NextRequest) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  try {
    const pool = getPool();
    const { rows } = await pool.query<{
      id: string;
      sid: string | null;
      created_at: Date | string;
      last_seen_at: Date | string;
      user_agent: string | null;
      revoked_at: Date | string | null;
    }>(
      `SELECT id::text, sid, created_at, last_seen_at, user_agent, revoked_at
         FROM dash_sessions
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2`,
      [gated.session.user_id, MAX_SESSIONS],
    );

    const items = rows.map((row) => ({
      id: row.id,
      sid: row.sid,
      created_at: toIso(row.created_at),
      last_seen_at: toIso(row.last_seen_at),
      user_agent:
        typeof row.user_agent === "string"
          ? row.user_agent.slice(0, 200)
          : null,
      revoked: row.revoked_at != null,
      current: row.sid != null && row.sid === gated.session.sid,
    }));

    return jsonOk({ items });
  } catch (err) {
    console.error("GET /auth/sessions failed", err);
    return jsonError(503, "degraded", "Could not list sessions.");
  }
}
