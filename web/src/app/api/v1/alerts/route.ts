import type { NextRequest } from "next/server";

import { sanitizeDisclosureCategory } from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/market-browse";
import {
  cappedAlertThreshold,
  MAX_ALERT_THRESHOLD,
} from "@/lib/api/finite-number";
import { readJsonBody } from "@/lib/api/read-json-body";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { toIso } from "@/lib/api/time";
import {
  isAlertType,
  NOTICE_ALERT_TYPES,
  normalizeSymbol,
} from "@/lib/api/symbol";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession, requireSessionAndCsrf } from "@/lib/auth/guard";
import { activeAlertQuota, createAlertRule, getPool, getStock } from "@/lib/db";

export const runtime = "nodejs";

/** Cap alert_rules list — unbounded SELECT used to OOM SSR / balloon JSON. */
export const MAX_ALERT_RULES = 500;

/**
 * GET /api/v1/alerts — session user's alert rules (active=true by default).
 * Optional `?symbol=` filters to one CSE symbol (case-insensitive normalize).
 */
export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  const url = request.nextUrl;
  const activeParam = url.searchParams.get("active");
  // Default true; only exact "true"/"false" — junk used to soft-accept as
  // cancelled (?active=TRUE / ?active=1 listed inactive rules).
  // Fail closed — non-string searchParams mocks must not soft-match.
  let activeOnly = true;
  if (activeParam != null) {
    if (typeof activeParam !== "string") {
      return jsonError(
        400,
        "validation_error",
        "active must be true or false.",
      );
    }
    if (activeParam === "true") {
      activeOnly = true;
    } else if (activeParam === "false") {
      activeOnly = false;
    } else {
      return jsonError(
        400,
        "validation_error",
        "active must be true or false.",
      );
    }
  }

  const symbolRaw = url.searchParams.get("symbol");
  let symbol: string | null = null;
  // Fail closed — non-string searchParams mocks used to throw on .trim.
  if (typeof symbolRaw === "string" && symbolRaw.trim()) {
    symbol = normalizeSymbol(symbolRaw);
    if (!symbol) {
      return jsonError(400, "invalid_symbol", "Invalid CSE symbol.");
    }
  }

  try {
    const pool = getPool();
    const params: unknown[] = [gated.session.user_id];
    const clauses = ["user_id = $1"];
    if (activeOnly) {
      clauses.push("active = TRUE");
    }
    if (symbol) {
      params.push(symbol);
      clauses.push(`symbol = $${params.length}`);
    }

    const result = await pool.query<{
      id: string | number;
      symbol: string;
      type: string;
      threshold: number | null;
      category: string | null;
      active: boolean;
      armed: boolean;
      created_at: Date | string;
      muted_until: Date | string | null;
    }>(
      `SELECT id, symbol, type, threshold, category, active, armed, created_at,
              muted_until
       FROM alert_rules
       WHERE ${clauses.join(" AND ")}
       ORDER BY id ASC
       LIMIT $${params.length + 1}`,
      [...params, MAX_ALERT_RULES],
    );

    const rules = result.rows.flatMap((row) => {
      const id = toSafePositiveInt(row.id);
      // Drop non-safe ids — Number(oversized) precision-loss used to alias rules.
      if (id == null) return [];
      if (!isAlertType(row.type)) return [];
      // Fail closed — only CSE SYMBOL_RE rows (not sanitize "?" fallback).
      const symbol = normalizeSymbol(row.symbol);
      if (!symbol) return [];
      // Finite + abs cap — upper-bound-only used to egress -1e308.
      const threshold = cappedAlertThreshold(toFiniteNumber(row.threshold));
      return [
        {
          id,
          symbol,
          type: row.type,
          // Finite-only + cap — NaN/±Inf / absurd magnitudes → null.
          threshold,
          // Strip C0/C1 + cap — parity with bot storage read path.
          category: sanitizeDisclosureCategory(row.category),
          // Strict === true — Boolean("false") used to mislabel armed/active.
          active: row.active === true,
          armed: row.armed === true,
          created_at: toIso(row.created_at),
          muted_until: toIso(row.muted_until),
        },
      ];
    });

    return jsonOk({ rules });
  } catch (err) {
    console.error("GET /alerts failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}

/**
 * POST /api/v1/alerts — create rule (CSRF). Auto-watch; idempotent return-existing.
 */
export async function POST(request: NextRequest) {
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
  const symbol = normalizeSymbol(obj.symbol);
  if (!symbol) {
    return jsonError(400, "invalid_symbol", "Invalid CSE symbol.");
  }

  if (!isAlertType(obj.type)) {
    return jsonError(
      400,
      "validation_error",
      "type must be a supported alert type (price, move, disclosure, volume, print, gap, notice, book, or filing metrics).",
    );
  }
  const alertType = obj.type;

  let threshold: number | null = null;
  const isNotice = (NOTICE_ALERT_TYPES as readonly string[]).includes(alertType);
  if (isNotice) {
    if (obj.threshold !== undefined && obj.threshold !== null) {
      return jsonError(
        400,
        "validation_error",
        "this alert type must not include a threshold.",
      );
    }
    threshold = null;
  } else {
    if (typeof obj.threshold !== "number" || !Number.isFinite(obj.threshold)) {
      return jsonError(
        400,
        "validation_error",
        "threshold must be a finite number.",
      );
    }
    // Mirror bot + dash UI: non-positive thresholds are dead/weird rules
    // (daily_move thr=0 never crosses; price ≤0 is not a CSE print).
    if (obj.threshold <= 0) {
      return jsonError(
        400,
        "validation_error",
        "threshold must be a positive number.",
      );
    }
    // Cap absurd magnitudes — MAX_VALUE / 1e308 used to persist dead rules.
    if (obj.threshold > MAX_ALERT_THRESHOLD) {
      return jsonError(
        400,
        "validation_error",
        "threshold is too large.",
      );
    }
    threshold = obj.threshold;
  }

  // Optional disclosure category filter (bot: /alert SYMBOL disclosure [CATEGORY]).
  // Non-disclosure types ignore category (mirror Storage.create_alert_rule).
  let category: string | null = null;
  if (obj.category !== undefined && obj.category !== null) {
    if (typeof obj.category !== "string") {
      return jsonError(
        400,
        "validation_error",
        "category must be a string when provided.",
      );
    }
    if (alertType === "disclosure") {
      category = sanitizeDisclosureCategory(obj.category);
    }
  }

  try {
    const stock = await getStock(symbol);
    if (!stock) {
      return jsonError(404, "not_found", "Unknown symbol.");
    }

    const quota = await activeAlertQuota(gated.session.user_id);
    if (quota.active_count >= quota.alert_quota_max) {
      return jsonError(
        429,
        "alert_quota_exceeded",
        "Active alert quota reached.",
      );
    }

    const { rule, created } = await createAlertRule(
      gated.session.user_id,
      symbol,
      alertType,
      threshold,
      category,
    );
    return jsonOk(rule, created ? 201 : 200);
  } catch (err) {
    console.error("POST /alerts failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}
