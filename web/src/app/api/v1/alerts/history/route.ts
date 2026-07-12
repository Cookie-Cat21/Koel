import type { NextRequest } from "next/server";

import {
  MAX_HISTORY_EVENT_KEY_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import {
  toNonNegativeSafeInt,
  toSafePositiveInt,
} from "@/lib/api/safe-int";
import { isAlertType, normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/** Cap fire-history message bodies so hostile DB text cannot balloon JSON. */
export const HISTORY_MESSAGE_TEXT_MAX = 4_000;
/** Bound OFFSET — same soft ceiling as market browse (no unbounded scans). */
export const MAX_HISTORY_OFFSET = 10_000;

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

/**
 * Derive delivery_status per API_CONTRACT_V1 (alert_log delivery-state).
 * Do not collapse delivered-unmarked into "sent" — that lies about message_sent.
 */
export function deriveDeliveryStatus(row: {
  message_sent: boolean;
  dead_lettered: boolean;
  delivery_attempted_ok: boolean;
}): "sent" | "dead_lettered" | "delivered_unmarked" | "retrying" {
  if (row.message_sent) return "sent";
  if (row.dead_lettered) return "dead_lettered";
  if (row.delivery_attempted_ok) return "delivered_unmarked";
  return "retrying";
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
  let symbol: string | null = null;
  if (symbolRaw != null && symbolRaw.trim()) {
    symbol = normalizeSymbol(symbolRaw);
    if (!symbol) {
      return jsonError(400, "invalid_symbol", "Invalid CSE symbol.");
    }
  }

  let limit = 50;
  const limitRaw = url.searchParams.get("limit");
  if (limitRaw != null) {
    // Digits-only SafeInteger — Number("1e2") / precision-loss must not pass.
    const n = toSafePositiveInt(limitRaw);
    if (n == null) {
      return jsonError(400, "validation_error", "limit must be a positive integer.");
    }
    limit = Math.min(n, 200);
  }

  let offset = 0;
  const offsetRaw = url.searchParams.get("offset");
  if (offsetRaw != null) {
    // Digits-only — reject scientific notation / float trunc aliases.
    const n = toNonNegativeSafeInt(offsetRaw, -1);
    if (n < 0) {
      return jsonError(400, "validation_error", "offset must be a non-negative integer.");
    }
    // Soft-cap like GET /symbols — reject pathological OFFSET scans.
    offset = Math.min(n, MAX_HISTORY_OFFSET);
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
      // Digits-only SafeInteger — no Math.trunc float alias / precision loss.
      const id = toSafePositiveInt(row.id);
      const rule_id = toSafePositiveInt(row.rule_id);
      if (id == null || rule_id == null) return [];
      if (!isAlertType(row.type)) return [];
      const attempts = toNonNegativeSafeInt(row.attempt_count, 0);
      // Fail closed — only CSE SYMBOL_RE (no sanitize "?" placeholder).
      const symbol = normalizeSymbol(row.symbol);
      if (!symbol) return [];
      const event_key =
        sanitizeDisclosureText(row.event_key, MAX_HISTORY_EVENT_KEY_LENGTH) ??
        "";
      // Strict === true — Boolean("false")/1 used to flip delivery_status.
      const message_sent = row.message_sent === true;
      const dead_lettered = row.dead_lettered === true;
      const delivery_attempted_ok = row.delivery_attempted_ok === true;
      return [
        {
          id,
          rule_id,
          symbol,
          type: row.type,
          fired_at: toIso(row.fired_at),
          message_sent,
          dead_lettered,
          attempt_count: attempts,
          delivery_status: deriveDeliveryStatus({
            message_sent,
            dead_lettered,
            delivery_attempted_ok,
          }),
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
