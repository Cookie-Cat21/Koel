import { headers } from "next/headers";

/**
 * Host header must be hostname[:port] only — no userinfo, path, scheme, or
 * whitespace. Spoofed values used to turn SSR fetch into a cookie-leaking
 * open redirect/SSRF.
 */
const SAFE_HOST_RE = /^[A-Za-z0-9.:[\]-]+$/;

export function isSafeInternalHost(host: string): boolean {
  if (!host || host.length > 253) return false;
  if (host.includes("..") || host.includes("@") || host.includes("/")) {
    return false;
  }
  if (/\s/.test(host)) return false;
  return SAFE_HOST_RE.test(host);
}

/**
 * Server-side GET to our own /api/v1/* with the incoming session cookie.
 * Pages stay thin; route handlers own Postgres + auth.
 *
 * Medium: root-relative paths only; never prefer client-spoofable
 * ``X-Forwarded-Host`` over ``Host`` (session cookie must not leave origin).
 */
export async function serverApiGet(path: string): Promise<Response> {
  // Reject absolute / scheme-relative URLs — callers must stay on-origin.
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new Error("serverApiGet path must be root-relative");
  }

  const h = await headers();
  // Prefer Host (request target). X-Forwarded-Host is attacker-controlled
  // when the edge does not strip it — do not use it for cookie-bearing fetch.
  const hostRaw = (h.get("host") ?? "localhost:3000").trim();
  const host = isSafeInternalHost(hostRaw) ? hostRaw : "localhost:3000";
  const proto = h.get("x-forwarded-proto") === "https" ? "https" : "http";
  const cookie = h.get("cookie") ?? "";
  const url = `${proto}://${host}${path}`;
  return fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
      cookie,
    },
    cache: "no-store",
  });
}
