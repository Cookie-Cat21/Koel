import type { NextRequest } from "next/server";

import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/**
 * GET /api/v1/alerts/history — fire history (alert_log) for session user.
 * Contract path (not /alerts/fires).
 */
export async function GET(request: NextRequest) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  const url = request.nextUrl;
  const symbolRaw = url.searchParams.get("symbol");
  const symbol =
    symbolRaw && symbolRaw.trim() ? symbolRaw.trim().toUpperCase() : null;

  let limit = 50;
  const limitRaw = url.searchParams.get("limit");
  if (limitRaw != null) {
    const n = Number(limitRaw);
    if (!Number.isSafeInteger(n) || n < 1) {
      return jsonError(400, "validation_error", "limit must be a positive integer.");
    }
    limit = Math.min(n, 200);
  }

  let offset = 0;
  const offsetRaw = url.searchParams.get("offset");
  if (offsetRaw != null) {
    const n = Number(offsetRaw);
    if (!Number.isSafeInteger(n) || n < 0) {
      return jsonError(400, "validation_error", "offset must be a non-negative integer.");
    }
    offset = n;
  }

  try {
    const pool = getPool();
    const params: unknown[] = [gated.session.user_id];
    let symbolClause = "";
    if (symbol) {
      params.push(symbol);
      symbolClause = ` AND r.symbol = $${params.length}`;
    }
    params.push(limit);
    const limitIdx = params.length;
    params.push(offset);
    const offsetIdx = params.length;

    const result = await pool.query<{
      id: string | number;
      rule_id: string | number;
      symbol: string;
      type: string;
      fired_at: Date | string;
      message_sent: boolean;
      message_text: string | null;
      event_key: string;
    }>(
      `SELECT
         l.id,
         l.rule_id,
         r.symbol,
         r.type,
         l.fired_at,
         l.message_sent,
         l.message_text,
         l.event_key
       FROM alert_log l
       JOIN alert_rules r ON r.id = l.rule_id
       WHERE r.user_id = $1${symbolClause}
       ORDER BY l.fired_at DESC, l.id DESC
       LIMIT $${limitIdx} OFFSET $${offsetIdx}`,
      params,
    );

    const events = result.rows.map((row) => ({
      id: Number(row.id),
      rule_id: Number(row.rule_id),
      symbol: row.symbol,
      type: row.type,
      fired_at: toIso(row.fired_at),
      message_sent: Boolean(row.message_sent),
      message_text: row.message_text,
      event_key: row.event_key,
    }));

    return jsonOk({ events, limit, offset });
  } catch (err) {
    console.error("GET /alerts/history failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
