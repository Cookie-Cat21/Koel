import type { NextRequest } from "next/server";

import { sanitizeDisclosureCategory } from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/market-browse";
import { toIso } from "@/lib/api/time";
import { isAlertType, normalizeSymbol } from "@/lib/api/symbol";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession, requireSessionAndCsrf } from "@/lib/auth/guard";
import { createAlertRule, getPool, getStock } from "@/lib/db";

export const runtime = "nodejs";

/**
 * GET /api/v1/alerts — session user's alert rules (active=true by default).
 * Optional `?symbol=` filters to one CSE symbol (case-insensitive normalize).
 */
export async function GET(request: NextRequest) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  const url = request.nextUrl;
  const activeParam = url.searchParams.get("active");
  // Default true; ?active=false lists cancelled; omit / true → active only.
  const activeOnly = activeParam === null || activeParam === "true";

  const symbolRaw = url.searchParams.get("symbol");
  let symbol: string | null = null;
  if (symbolRaw != null && symbolRaw.trim()) {
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
    }>(
      `SELECT id, symbol, type, threshold, category, active, armed, created_at
       FROM alert_rules
       WHERE ${clauses.join(" AND ")}
       ORDER BY id ASC`,
      params,
    );

    const rules = result.rows.flatMap((row) => {
      const id = Number(row.id);
      // Drop non-safe ids — JSON.stringify(NaN) becomes null; unsafe ints
      // lose precision and can alias the wrong rule.
      if (!Number.isSafeInteger(id) || id <= 0) return [];
      return [
        {
          id,
          symbol: row.symbol,
          type: row.type,
          // Finite-only — NaN/±Inf threshold from a poisoned row → null.
          threshold: toFiniteNumber(row.threshold),
          // Strip C0/C1 + cap — parity with bot storage read path.
          category: sanitizeDisclosureCategory(row.category),
          active: Boolean(row.active),
          armed: Boolean(row.armed),
          created_at: toIso(row.created_at),
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
  const gated = requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return jsonError(400, "validation_error", "Invalid JSON body.");
  }

  if (typeof body !== "object" || body === null) {
    return jsonError(400, "validation_error", "Invalid request body.");
  }

  const obj = body as Record<string, unknown>;
  const symbol = normalizeSymbol(obj.symbol);
  if (!symbol) {
    return jsonError(400, "invalid_symbol", "Invalid CSE symbol.");
  }

  if (!isAlertType(obj.type)) {
    return jsonError(
      400,
      "validation_error",
      "type must be price_above, price_below, daily_move, or disclosure.",
    );
  }
  const alertType = obj.type;

  let threshold: number | null = null;
  if (alertType === "disclosure") {
    if (obj.threshold !== undefined && obj.threshold !== null) {
      return jsonError(
        400,
        "validation_error",
        "disclosure alerts must not include a threshold.",
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
