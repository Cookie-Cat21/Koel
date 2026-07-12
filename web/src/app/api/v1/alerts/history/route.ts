import type { NextRequest } from "next/server";

import {
  MAX_HISTORY_EVENT_KEY_LENGTH,
  MAX_HISTORY_SYMBOL_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/** Cap fire-history message bodies so hostile DB text cannot balloon JSON. */
export const HISTORY_MESSAGE_TEXT_MAX = 4_000;

const CTRL_RE = /[\u0000-\u001F\u007F-\u009F]/g;

function sanitizeHistoryMessage(
  raw: string | null | undefined,
): string | null {
  if (raw == null) return null;
  const cleaned = raw.replace(CTRL_RE, "").trim();
  if (!cleaned) return null;
  return cleaned.length > HISTORY_MESSAGE_TEXT_MAX
    ? cleaned.slice(0, HISTORY_MESSAGE_TEXT_MAX - 1).trimEnd() + "…"
    : cleaned;
}

function toSafeInt(raw: unknown, fallback = 0): number {
  const n = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isFinite(n)) return fallback;
  return Math.trunc(n);
}

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
      dead_lettered: boolean;
      attempt_count: string | number;
      delivery_attempted_ok: boolean;
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
         l.dead_lettered,
         l.attempt_count,
         l.delivery_attempted_ok,
         l.message_text,
         l.event_key
       FROM alert_log l
       JOIN alert_rules r ON r.id = l.rule_id
       WHERE r.user_id = $1${symbolClause}
       ORDER BY l.fired_at DESC, l.id DESC
       LIMIT $${limitIdx} OFFSET $${offsetIdx}`,
      params,
    );

    const events = result.rows.flatMap((row) => {
      const id = toSafeInt(row.id, Number.NaN);
      const rule_id = toSafeInt(row.rule_id, Number.NaN);
      // Drop non-safe ids — JSON.stringify(NaN) becomes null and breaks clients;
      // unsafe ints lose precision and can alias the wrong fire row.
      if (!Number.isSafeInteger(id) || !Number.isSafeInteger(rule_id)) return [];
      if (id <= 0 || rule_id <= 0) return [];
      const attempts = toSafeInt(row.attempt_count, 0);
      const symbol =
        sanitizeDisclosureText(row.symbol, MAX_HISTORY_SYMBOL_LENGTH) ?? "?";
      const event_key =
        sanitizeDisclosureText(row.event_key, MAX_HISTORY_EVENT_KEY_LENGTH) ??
        "";
      return [
        {
          id,
          rule_id,
          symbol,
          type: row.type,
          fired_at: toIso(row.fired_at),
          message_sent: Boolean(row.message_sent),
          dead_lettered: Boolean(row.dead_lettered),
          attempt_count: attempts < 0 ? 0 : attempts,
          delivery_status:
            row.message_sent
              ? "sent"
              : row.dead_lettered
                ? "dead_lettered"
                : row.delivery_attempted_ok
                  ? "sent"
                  : "retrying",
          message_text: sanitizeHistoryMessage(row.message_text),
          event_key,
        },
      ];
    });

    return jsonOk({ events, limit, offset });
  } catch (err) {
    console.error("GET /alerts/history failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
