import type { NextRequest } from "next/server";

import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/**
 * GET /api/v1/alerts — session user's alert rules (active=true by default).
 */
export async function GET(request: NextRequest) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  const url = request.nextUrl;
  const activeParam = url.searchParams.get("active");
  // Default true; ?active=false lists cancelled; omit / true → active only.
  const activeOnly = activeParam === null || activeParam === "true";

  try {
    const pool = getPool();
    const result = await pool.query<{
      id: string | number;
      symbol: string;
      type: string;
      threshold: number | null;
      active: boolean;
      armed: boolean;
      created_at: Date | string;
    }>(
      activeOnly
        ? `SELECT id, symbol, type, threshold, active, armed, created_at
           FROM alert_rules
           WHERE user_id = $1 AND active = TRUE
           ORDER BY id ASC`
        : `SELECT id, symbol, type, threshold, active, armed, created_at
           FROM alert_rules
           WHERE user_id = $1
           ORDER BY id ASC`,
      [gated.session.user_id],
    );

    const rules = result.rows.map((row) => ({
      id: Number(row.id),
      symbol: row.symbol,
      type: row.type,
      threshold: row.threshold == null ? null : Number(row.threshold),
      active: Boolean(row.active),
      armed: Boolean(row.armed),
      created_at: toIso(row.created_at),
    }));

    return jsonOk({ rules });
  } catch (err) {
    console.error("GET /alerts failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
