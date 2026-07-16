import { randomBytes } from "node:crypto";
import type { NextRequest } from "next/server";

import {
  MAX_HISTORY_EVENT_KEY_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { cappedAlertThreshold } from "@/lib/api/finite-number";
import { toFiniteNumber } from "@/lib/api/market-browse";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { isAlertType, normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSessionAndCsrf } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type RouteContext = { params: Promise<{ id: string }> };

function dryRunMessage(row: {
  id: number;
  symbol: string;
  type: string;
  threshold: number | null;
  category: string | null;
}): string {
  const bits = [`[dry-run] Chime test fire for ${row.symbol}`, `Type: ${row.type}`];
  if (row.threshold != null) bits.push(`Threshold: ${row.threshold}`);
  if (row.category) bits.push(`Category: ${row.category}`);
  bits.push("No Telegram message was sent.");
  bits.push("");
  bits.push("Not financial advice — informational only.");
  return bits.join("\n");
}

/**
 * POST /api/v1/alerts/{id}/test-fire — audit-only dry run, no Telegram send.
 */
export async function POST(request: NextRequest, context: RouteContext) {
  const gated = await requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

  const { id: rawId } = await context.params;
  const ruleId = toSafePositiveInt(rawId);
  if (ruleId == null) {
    return jsonError(400, "validation_error", "Invalid alert id.");
  }

  try {
    const pool = getPool();
    const rule = await pool.query<{
      id: string | number;
      symbol: string;
      type: string;
      threshold: number | string | null;
      category: string | null;
    }>(
      `SELECT id, symbol, type, threshold, category
       FROM alert_rules
       WHERE id = $1 AND user_id = $2 AND active
       LIMIT 1`,
      [ruleId, gated.session.user_id],
    );
    const row = rule.rows[0];
    if (!row) {
      return jsonError(404, "not_found", "Alert not found.");
    }

    const id = toSafePositiveInt(row.id);
    const symbol = normalizeSymbol(row.symbol);
    if (id == null || !symbol || !isAlertType(row.type)) {
      return jsonError(404, "not_found", "Alert not found.");
    }
    const mapped = {
      id,
      symbol,
      type: row.type,
      threshold: cappedAlertThreshold(toFiniteNumber(row.threshold)),
      category: sanitizeDisclosureText(row.category, 64),
    };
    const message = dryRunMessage(mapped);
    const eventKey =
      sanitizeDisclosureText(
        `dry_run:${id}:${Date.now()}:${randomBytes(4).toString("hex")}`,
        MAX_HISTORY_EVENT_KEY_LENGTH,
      ) ?? `dry_run:${id}`;

    const inserted = await pool.query<{
      id: string | number;
      fired_at: Date | string;
    }>(
      `INSERT INTO alert_log (
         rule_id, snapshot_id, event_key, message_sent, message_text,
         delivery_attempted_ok
       )
       VALUES ($1, NULL, $2, TRUE, $3, TRUE)
       RETURNING id, fired_at`,
      [id, eventKey, message],
    );
    const audit = inserted.rows[0];
    const auditId = audit ? toSafePositiveInt(audit.id) : null;

    return jsonOk({
      dry_run: true,
      alert_log_id: auditId,
      message,
      fired_at: toIso(audit?.fired_at ?? null),
    });
  } catch (err) {
    console.error("POST /alerts/[id]/test-fire failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
