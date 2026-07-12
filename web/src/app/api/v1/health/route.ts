import type { NextRequest } from "next/server";

import { toIso } from "@/lib/api/time";
import {
  toNonNegativeSafeInt,
  toSafePositiveInt,
} from "@/lib/api/safe-int";
import { normalizeSymbol } from "@/lib/api/symbol";
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
  // Digits-only SafeInteger — Number("3e3") / floats must not soft-accept.
  const n = toSafePositiveInt(raw);
  if (n == null || n > 30_000) {
    return HEALTH_PROXY_TIMEOUT_MS_DEFAULT;
  }
  return n;
}

type BriefQueueHint = {
  pending_briefs?: number;
  pdf_enrich?: {
    in_flight_tasks?: number;
    last_batch_size?: number;
    batches_started?: number;
  };
};

type PollerHealth = {
  last_tick_at?: string | null;
  last_tick_ok?: boolean;
  price_poll_ok?: boolean;
  disclosure_poll_ok?: boolean;
  lock_held_skip?: boolean;
  last_error?: string | null;
  watched_missing?: string[];
  circuits?: Record<string, unknown>;
  /** Ops hint only — never drives ok/degraded. */
  brief_queue?: BriefQueueHint;
  [key: string]: unknown;
};

/** Cap hostile HEALTH_URL strings so ops UI / JSON cannot balloon. */
export const HEALTH_STRING_MAX = 512;
export const HEALTH_WATCHED_MISSING_MAX = 64;
/** Bound circuit map size from a hostile HEALTH_URL body. */
export const HEALTH_CIRCUITS_MAX = 32;
/** Bound HEALTH_URL JSON body bytes before parse (ops payload is tiny). */
export const HEALTH_PROXY_BODY_MAX_BYTES = 64_000;

const CIRCUIT_STATES = new Set(["closed", "open", "half_open"]);

/**
 * HEALTH_URL must be loopback HTTP only. A mis-set / injected env must not
 * turn the session-gated health proxy into an open SSRF (metadata, LAN).
 * Matches poller health loopback posture (http://127.0.0.1:8080/health).
 */
export function isAllowedHealthProxyUrl(raw: string): boolean {
  const trimmed = raw.trim();
  if (!trimmed || trimmed.length > 512) return false;
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return false;
  }
  if (parsed.protocol !== "http:") return false;
  if (parsed.username || parsed.password) return false;
  const host = parsed.hostname.toLowerCase();
  if (host !== "127.0.0.1" && host !== "localhost" && host !== "::1") {
    return false;
  }
  // Reject fragment weirdness that is not a health probe.
  if (parsed.hash) return false;
  return true;
}

/** Parse loopback health `brief_queue` (fail-soft; omit empty). */
export function parseBriefQueue(raw: unknown): BriefQueueHint | undefined {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return undefined;
  const obj = raw as Record<string, unknown>;
  const hint: BriefQueueHint = {};

  // Digits-only SafeInteger — Number.isFinite+Math.floor used to soft-accept
  // floats / sci-notation strings into ops JSON.
  const pending = toNonNegativeSafeInt(obj.pending_briefs, -1);
  if (pending >= 0) {
    hint.pending_briefs = pending;
  }

  const pe = obj.pdf_enrich;
  if (pe && typeof pe === "object" && !Array.isArray(pe)) {
    const src = pe as Record<string, unknown>;
    const pdf: NonNullable<BriefQueueHint["pdf_enrich"]> = {};
    for (const key of [
      "in_flight_tasks",
      "last_batch_size",
      "batches_started",
    ] as const) {
      const n = toNonNegativeSafeInt(src[key], -1);
      if (n >= 0) {
        pdf[key] = n;
      }
    }
    if (Object.keys(pdf).length > 0) {
      hint.pdf_enrich = pdf;
    }
  }

  return Object.keys(hint).length > 0 ? hint : undefined;
}

function sanitizeHealthString(raw: unknown): string | null | undefined {
  if (raw === null) return null;
  if (typeof raw !== "string") return undefined;
  const cleaned = raw.replace(/[\u0000-\u001F\u007F-\u009F]/g, "").trim();
  if (!cleaned) return null;
  return cleaned.length > HEALTH_STRING_MAX
    ? cleaned.slice(0, HEALTH_STRING_MAX)
    : cleaned;
}

function sanitizeWatchedMissing(raw: unknown): string[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  const out: string[] = [];
  for (const item of raw) {
    // Fail closed — only CSE SYMBOL_RE (no sanitize length-cap fallback).
    // Hostile HEALTH_URL used to egress 512-char non-ticker strings into ops JSON.
    const sym = normalizeSymbol(item);
    if (!sym) continue;
    out.push(sym);
    if (out.length >= HEALTH_WATCHED_MISSING_MAX) break;
  }
  return out;
}


/**
 * Allowlist circuit snapshots only — never raw-spread a hostile nested map
 * (unbounded keys / string payloads can balloon the ops JSON).
 */
export function sanitizeCircuits(
  raw: unknown,
): Record<string, Record<string, unknown>> | undefined {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return undefined;
  const out: Record<string, Record<string, unknown>> = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (Object.keys(out).length >= HEALTH_CIRCUITS_MAX) break;
    const name = sanitizeHealthString(key);
    if (!name || name.length > 64) continue;
    if (!value || typeof value !== "object" || Array.isArray(value)) continue;
    const src = value as Record<string, unknown>;
    const entry: Record<string, unknown> = {};
    const cName = sanitizeHealthString(src.name);
    if (cName) entry.name = cName.length > 64 ? cName.slice(0, 64) : cName;
    const state = sanitizeHealthString(src.state);
    if (state && CIRCUIT_STATES.has(state)) entry.state = state;
    for (const numKey of [
      "failures",
      "fail_max",
      "reset_timeout_seconds",
    ] as const) {
      // Digits-only SafeInteger — reject float / sci-notation soft-accept.
      const n = toNonNegativeSafeInt(src[numKey], -1);
      if (n >= 0) {
        entry[numKey] = n;
      }
    }
    if (typeof src.half_open_trial === "boolean") {
      entry.half_open_trial = src.half_open_trial;
    }
    if (Object.keys(entry).length > 0) {
      out[name] = entry;
    }
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

/**
 * Pick typed poller fields only — never raw-spread a nested `body.poller`
 * (that overwrote sanitized booleans / watched_missing with hostile shapes).
 * Omitted / wrong-typed keys stay ``undefined`` so a nested merge cannot
 * clobber a good top-level value with a forced ``null``.
 */
export function sanitizePollerHealth(raw: unknown): PollerHealth | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const body = raw as Record<string, unknown>;
  const poller: PollerHealth = {};

  if ("last_tick_at" in body) {
    if (body.last_tick_at === null) {
      poller.last_tick_at = null;
    } else {
      const cleaned = sanitizeHealthString(body.last_tick_at);
      // Require parseable ISO — sanitize-only left hostile non-dates in ops JSON.
      poller.last_tick_at =
        cleaned === undefined ? null : cleaned == null ? null : toIso(cleaned);
    }
  }
  if (typeof body.last_tick_ok === "boolean") {
    poller.last_tick_ok = body.last_tick_ok;
  }
  if (typeof body.price_poll_ok === "boolean") {
    poller.price_poll_ok = body.price_poll_ok;
  }
  if (typeof body.disclosure_poll_ok === "boolean") {
    poller.disclosure_poll_ok = body.disclosure_poll_ok;
  }
  if (typeof body.lock_held_skip === "boolean") {
    poller.lock_held_skip = body.lock_held_skip;
  }
  if ("last_error" in body) {
    poller.last_error = sanitizeHealthString(body.last_error) ?? null;
  }
  if ("watched_missing" in body) {
    poller.watched_missing = sanitizeWatchedMissing(body.watched_missing) ?? [];
  }
  const circuits = sanitizeCircuits(body.circuits);
  if (circuits) {
    poller.circuits = circuits;
  }
  const brief = parseBriefQueue(body.brief_queue);
  if (brief) {
    poller.brief_queue = brief;
  }
  return poller;
}

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
    // Fail closed — non-loopback / https / credentialed URLs must not fetch.
    if (!isAllowedHealthProxyUrl(healthUrl)) {
      console.error("GET /health HEALTH_URL rejected (not loopback http)");
      poller = {
        last_tick_ok: false,
        last_error: "health_url_unreachable",
      };
    } else {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), healthProxyTimeoutMs());
      try {
        const res = await fetch(healthUrl, {
          method: "GET",
          signal: ctrl.signal,
          // Fail closed — open redirects must not bounce into metadata/LAN.
          redirect: "error",
          headers: { Accept: "application/json" },
        });
        // Early-reject claimed Content-Length before allocating the body
        // (parity with serverApiGet — hostile loopback still must not OOM).
        const lenHeader = res.headers.get("content-length");
        if (lenHeader != null && lenHeader.trim()) {
          const claimed = toNonNegativeSafeInt(lenHeader.trim(), -1);
          if (claimed < 0 || claimed > HEALTH_PROXY_BODY_MAX_BYTES) {
            throw new Error("health_url_body_too_large");
          }
        }
        // Keep abort armed through body read — hung / huge JSON must not OOM.
        const rawText = await res.text().catch(() => "");
        if (rawText.length > HEALTH_PROXY_BODY_MAX_BYTES) {
          throw new Error("health_url_body_too_large");
        }
        let body: Record<string, unknown> | null = null;
        try {
          const parsed: unknown = rawText ? JSON.parse(rawText) : null;
          if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            body = parsed as Record<string, unknown>;
          }
        } catch {
          body = null;
        }
        if (body && typeof body === "object") {
          const startedClean = sanitizeHealthString(body.started_at);
          const started = startedClean ? toIso(startedClean) : null;
          if (started) {
            startedAt = started;
          }
          // Sanitize top-level + nested separately — never raw-spread nested
          // (hostile HEALTH_URL used to overwrite typed booleans / watched_missing).
          const top = sanitizePollerHealth(body);
          const nested = sanitizePollerHealth(body.poller);
          if (top || nested) {
            const pick = (p: PollerHealth | null): Partial<PollerHealth> => {
              if (!p) return {};
              const out: Partial<PollerHealth> = {};
              for (const [key, value] of Object.entries(p)) {
                if (value !== undefined) {
                  (out as Record<string, unknown>)[key] = value;
                }
              }
              return out;
            };
            poller = { ...pick(top), ...pick(nested) };
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
