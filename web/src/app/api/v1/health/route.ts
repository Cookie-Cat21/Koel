import type { NextRequest } from "next/server";

import { toIso } from "@/lib/api/time";
import { jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/** Process start — used when HEALTH_URL is unset (DB-only health). */
const PROCESS_STARTED_AT = new Date().toISOString();

/** Default bound for HEALTH_URL proxy (headers + body). */
export const HEALTH_PROXY_TIMEOUT_MS_DEFAULT = 3000;

/** Bound HEALTH_URL proxy. Fail-closed on bad/non-positive env → default. */
export function healthProxyTimeoutMs(): number {
  const raw = (process.env.HEALTH_PROXY_TIMEOUT_MS ?? "").trim();
  if (!raw) return HEALTH_PROXY_TIMEOUT_MS_DEFAULT;
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0 || n > 30_000) {
    return HEALTH_PROXY_TIMEOUT_MS_DEFAULT;
  }
  return n;
}

type PollerHealth = {
  last_tick_at?: string | null;
  last_tick_ok?: boolean;
  price_poll_ok?: boolean;
  disclosure_poll_ok?: boolean;
  lock_held_skip?: boolean;
  last_error?: string | null;
  watched_missing?: string[];
  circuits?: Record<string, unknown>;
  [key: string]: unknown;
};

/**
 * GET /api/v1/health — ops-gated (valid session). DB ping + optional poller proxy.
 * Postgres only from this handler; optional HEALTH_URL for poller detail.
 */
export async function GET(request: NextRequest) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  let dbOk = false;
  let lastSnapshotAt: string | null = null;
  let startedAt = PROCESS_STARTED_AT;
  let poller: PollerHealth | null = null;

  try {
    const pool = getPool();
    await pool.query("SELECT 1");
    dbOk = true;
    const snap = await pool.query<{ max_ts: Date | string | null }>(
      `SELECT MAX(ts) AS max_ts FROM price_snapshots`,
    );
    lastSnapshotAt = toIso(snap.rows[0]?.max_ts ?? null);
  } catch (err) {
    console.error("GET /health db ping failed", err);
    dbOk = false;
  }

  const healthUrl = (process.env.HEALTH_URL ?? "").trim();
  if (healthUrl) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), healthProxyTimeoutMs());
    // Avoid keeping the event loop awake solely for this timer (Node).
    timer.unref?.();
    try {
      const res = await fetch(healthUrl, {
        method: "GET",
        signal: ctrl.signal,
        headers: { Accept: "application/json" },
      });
      // Keep abort armed through body parse — hung JSON must not outlive budget.
      const body = (await res.json().catch(() => null)) as Record<
        string,
        unknown
      > | null;
      if (body && typeof body === "object") {
        if (typeof body.started_at === "string") {
          startedAt = body.started_at;
        }
        poller = {
          last_tick_at:
            typeof body.last_tick_at === "string" || body.last_tick_at === null
              ? (body.last_tick_at as string | null)
              : null,
          last_tick_ok:
            typeof body.last_tick_ok === "boolean"
              ? body.last_tick_ok
              : undefined,
          price_poll_ok:
            typeof body.price_poll_ok === "boolean"
              ? body.price_poll_ok
              : undefined,
          disclosure_poll_ok:
            typeof body.disclosure_poll_ok === "boolean"
              ? body.disclosure_poll_ok
              : undefined,
          lock_held_skip:
            typeof body.lock_held_skip === "boolean"
              ? body.lock_held_skip
              : undefined,
          last_error:
            typeof body.last_error === "string" || body.last_error === null
              ? (body.last_error as string | null)
              : null,
          watched_missing: Array.isArray(body.watched_missing)
            ? (body.watched_missing as unknown[]).filter(
                (s): s is string => typeof s === "string",
              )
            : undefined,
          circuits:
            body.circuits &&
            typeof body.circuits === "object" &&
            !Array.isArray(body.circuits)
              ? (body.circuits as Record<string, unknown>)
              : undefined,
        };
        // Prefer nested poller if present
        if (body.poller && typeof body.poller === "object") {
          poller = { ...poller, ...(body.poller as PollerHealth) };
        }
      }
    } catch (err) {
      console.error("GET /health HEALTH_URL fetch failed", err);
      poller = {
        last_tick_ok: false,
        last_error: "health_url_unreachable",
      };
    } finally {
      clearTimeout(timer);
    }
  }

  const missing =
    poller != null && Array.isArray(poller.watched_missing)
      ? poller.watched_missing
      : [];
  // Fail closed for ops when the proxied poller reports any component failure.
  const pollerDegraded =
    poller != null &&
    (poller.last_tick_ok === false ||
      poller.price_poll_ok === false ||
      poller.disclosure_poll_ok === false ||
      poller.last_error === "health_url_unreachable" ||
      missing.length > 0);
  const status = dbOk && !pollerDegraded ? "ok" : "degraded";
  const httpStatus = status === "ok" ? 200 : 503;

  const payload: Record<string, unknown> = {
    status,
    db_ok: dbOk,
    started_at: startedAt,
    last_snapshot_at: lastSnapshotAt,
  };
  if (poller != null) {
    payload.poller = poller;
  } else {
    payload.poller = null;
  }

  if (!dbOk && httpStatus === 503) {
    // Still return structured body for ops
    return jsonOk(payload, 503);
  }

  return jsonOk(payload, httpStatus);
}
