import { readBoundedResponseText } from "@/lib/api/read-bounded-text";
import { headers } from "next/headers";

/**
 * Host header must be hostname[:port] only — no userinfo, path, scheme, or
 * whitespace. Spoofed values used to turn SSR fetch into a cookie-leaking
 * open redirect/SSRF.
 */
const SAFE_HOST_RE = /^[A-Za-z0-9.:[\]-]+$/;

export function isSafeInternalHost(host: unknown): boolean {
  // Fail closed — non-strings used to throw on .includes / .length.
  if (typeof host !== "string" || !host || host.length > 253) return false;
  if (host.includes("..") || host.includes("@") || host.includes("/")) {
    return false;
  }
  if (/\s/.test(host)) return false;
  return SAFE_HOST_RE.test(host);
}

/**
 * Strip optional ``:port`` / ``[ipv6]:port`` so loopback checks compare names.
 */
export function hostnameOnly(host: unknown): string {
  // Fail closed — non-strings used to throw on .trim mid-origin resolve.
  if (typeof host !== "string") return "";
  const bare = host.trim().toLowerCase();
  if (!bare) return "";
  if (bare.startsWith("[")) {
    const end = bare.indexOf("]");
    return end > 0 ? bare.slice(1, end) : bare;
  }
  if (bare.startsWith("localhost:")) return "localhost";
  if (/^(\d{1,3}\.){3}\d{1,3}:\d+$/.test(bare)) {
    return bare.slice(0, bare.lastIndexOf(":"));
  }
  return bare;
}

/** True for loopback hostname/IP (optional :port / brackets). */
export function isLoopbackHost(host: unknown): boolean {
  // Fail closed — non-strings must not rely solely on hostnameOnly soft-empty.
  if (typeof host !== "string") return false;
  const name = hostnameOnly(host);
  return (
    name === "localhost" ||
    name === "127.0.0.1" ||
    name === "::1" ||
    name === "0:0:0:0:0:0:0:1"
  );
}

/**
 * Vercel-injected deployment hostname (build/runtime system env — never
 * derived from the incoming request), if this process is running there.
 * There is no shared loopback listener across a serverless invocation, so
 * on Vercel the ``127.0.0.1:$PORT`` fallback below is unreachable and every
 * SSR page using ``serverApiGet`` would degrade. Prefer the stable
 * production alias when set, else the per-deployment URL.
 */
function resolveVercelTrustedOrigin(env: NodeJS.ProcessEnv): string {
  const host = env.VERCEL_PROJECT_PRODUCTION_URL || env.VERCEL_URL;
  if (typeof host !== "string" || !host.trim()) return "";
  const bare = host.trim();
  if (!isSafeInternalHost(bare)) return "";
  return `https://${bare}`;
}

/**
 * Origin for cookie-bearing SSR → /api/v1 fetches.
 *
 * Medium: never trust client ``Host`` / ``X-Forwarded-*`` — those used to
 * exfiltrate the session cookie to an attacker-controlled host. Prefer
 * ``DASH_INTERNAL_ORIGIN`` (loopback only), else the Vercel platform's own
 * system env var (also not client-controlled), else ``http://127.0.0.1:$PORT``.
 */
export function resolveInternalOrigin(
  env: NodeJS.ProcessEnv = process.env,
): string {
  // Fail closed — non-string env mocks used to throw on .trim mid SSR origin
  // (parity getDashAuthConfig / cookieSecure typeof guards).
  const fromEnvRaw = env.DASH_INTERNAL_ORIGIN;
  const fromEnv =
    typeof fromEnvRaw === "string" ? fromEnvRaw.trim() : "";
  if (fromEnv) {
    try {
      const u = new URL(fromEnv);
      if (
        (u.protocol === "http:" || u.protocol === "https:") &&
        !u.username &&
        !u.password &&
        isSafeInternalHost(u.host) &&
        isLoopbackHost(u.host)
      ) {
        return u.origin;
      }
    } catch {
      /* fall through */
    }
  }
  const vercelOrigin = resolveVercelTrustedOrigin(env);
  if (vercelOrigin) return vercelOrigin;
  const portEnv = env.PORT;
  const portRaw = typeof portEnv === "string" ? portEnv.trim() : "";
  const port = /^\d{1,5}$/.test(portRaw) ? portRaw : "3000";
  const n = Number(port);
  if (!Number.isInteger(n) || n < 1 || n > 65535) {
    return "http://127.0.0.1:3000";
  }
  return `http://127.0.0.1:${port}`;
}

/**
 * Cap SSR API paths before startsWith / regex — multi-MB forged paths used
 * to burn CPU in ``serverApiGet`` before the /api/v1 gate rejected them.
 */
export const MAX_SERVER_API_PATH_LENGTH = 512;

/**
 * Cookie-bearing SSR paths must stay under ``/api/v1/`` — reject ``..`` /
 * backslash / control chars / absolute URLs that used to path-traverse or
 * ship the session cookie off-origin.
 */
export function isSafeServerApiPath(path: unknown): boolean {
  // Fail closed — non-strings used to throw on .startsWith mid-SSR fetch.
  if (typeof path !== "string" || !path) return false;
  if (path.length > MAX_SERVER_API_PATH_LENGTH) return false;
  if (!path.startsWith("/") || path.startsWith("//")) return false;
  if (path.includes("://") || path.includes("\\") || path.includes("..")) {
    return false;
  }
  if (/[\u0000-\u001F\u007F]/.test(path)) return false;
  const pathOnly = path.split("?", 1)[0] ?? path;
  return pathOnly === "/api/v1" || pathOnly.startsWith("/api/v1/");
}

/** Abort budget for cookie-bearing SSR → /api/v1 (pages stay snappy). */
export const SERVER_API_TIMEOUT_MS = 10_000;

/** Cap SSR response body before page ``res.json()`` (browse payloads are tiny). */
export const SERVER_API_BODY_MAX_BYTES = 1_048_576;

/**
 * Cap Cookie header forwarded into loopback SSR fetch.
 * Minted session+csrf cookies are well under 1KB; a multi-MB Cookie used to
 * amplify into the internal fetch and pressure the SSR worker.
 */
export const SERVER_API_COOKIE_MAX_CHARS = 4_096;

/**
 * Server-side GET to our own /api/v1/* with the incoming session cookie.
 * Pages stay thin; route handlers own Postgres + auth.
 *
 * Medium: root-relative ``/api/v1/*`` only; origin is loopback /
 * ``DASH_INTERNAL_ORIGIN`` — never client ``Host`` (session cookie must not
 * leave the process). ``redirect: "error"`` so Cookie cannot follow off-box.
 * Bound timeout + body bytes so a stuck / hostile route cannot hang or OOM
 * the SSR worker (parity with HEALTH_URL proxy bounds). Cap Cookie header
 * length; force ``application/json`` Content-Type (never reflect upstream).
 */
export async function serverApiGet(path: string): Promise<Response> {
  if (!isSafeServerApiPath(path)) {
    throw new Error("serverApiGet path must be root-relative /api/v1/*");
  }

  const h = await headers();
  // Cookie header only — do not derive fetch URL from client Host / XFH.
  const cookieRaw = h.get("cookie") ?? "";
  // Fail closed — overlong Cookie must not amplify into the loopback fetch.
  if (cookieRaw.length > SERVER_API_COOKIE_MAX_CHARS) {
    return new Response(JSON.stringify({ error: { code: "degraded" } }), {
      status: 502,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }
  const cookie = cookieRaw;
  const url = `${resolveInternalOrigin()}${path}`;
  // Vercel Deployment Protection (SSO) blocks server→self fetches unless the
  // automation bypass secret is present. Without it, SSR often gets an HTML
  // login shell (200) and pages parse empty API payloads.
  const bypassRaw =
    process.env.VERCEL_AUTOMATION_BYPASS_SECRET ??
    process.env.DASH_VERCEL_PROTECTION_BYPASS;
  const bypass =
    typeof bypassRaw === "string" && bypassRaw.trim()
      ? bypassRaw.trim()
      : "";
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), SERVER_API_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
        cookie,
        ...(bypass
          ? {
              "x-vercel-protection-bypass": bypass,
              "x-vercel-set-bypass-cookie": "true",
            }
          : {}),
      },
      cache: "no-store",
      // Fail closed — open redirects must not bounce the Cookie header off-box.
      redirect: "error",
      signal: ctrl.signal,
    });
    // Stream-bound body — missing / understated Content-Length must not let
    // res.text() allocate past the cap (parity readJsonBody / client mutate).
    const bounded = await readBoundedResponseText(
      res,
      SERVER_API_BODY_MAX_BYTES,
    );
    if (!bounded.ok) {
      return new Response(JSON.stringify({ error: { code: "degraded" } }), {
        status: 502,
        headers: { "Content-Type": "application/json; charset=utf-8" },
      });
    }
    // Force JSON — never reflect a hostile upstream Content-Type / statusText
    // into pages (statusText used to echo unbounded Reason-Phrase junk).
    return new Response(bounded.text, {
      status: res.status,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  } catch {
    return new Response(JSON.stringify({ error: { code: "degraded" } }), {
      status: 502,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  } finally {
    clearTimeout(timer);
  }
}
