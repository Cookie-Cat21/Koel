import type { NextRequest } from "next/server";
import type { NextResponse } from "next/server";

import { getDashAuthConfig, SESSION_COOKIE } from "./config";
import { csrfTokensMatch, CSRF_HEADER, readCsrfCookie } from "./csrf";
import { jsonError } from "./errors";
import { type SessionPayload, verifySessionToken } from "./session";

export type SessionOk = { ok: true; session: SessionPayload };
export type GuardFail = { ok: false; response: NextResponse };
export type SessionResult = SessionOk | GuardFail;

/** Resolve signed session from HttpOnly cookie. user_id is the sole trust anchor. */
export function requireSession(request: NextRequest): SessionResult {
  const cfg = getDashAuthConfig();
  if (!cfg.sessionSecret) {
    return {
      ok: false,
      response: jsonError(
        503,
        "degraded",
        "DASH_SESSION_SECRET is not configured.",
      ),
    };
  }

  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return {
      ok: false,
      response: jsonError(401, "unauthorized", "Authentication required."),
    };
  }

  const session = verifySessionToken(token, cfg.sessionSecret);
  if (!session) {
    return {
      ok: false,
      response: jsonError(401, "unauthorized", "Authentication required."),
    };
  }

  return { ok: true, session };
}

/**
 * Session + CSRF for POST/PATCH/PUT/DELETE under /api/v1 (including logout).
 * Login (`POST /auth/demo`) is the only CSRF-exempt mutation.
 */
export function requireSessionAndCsrf(request: NextRequest): SessionResult {
  const session = requireSession(request);
  if (!session.ok) return session;

  const header = request.headers.get(CSRF_HEADER);
  const cookie = readCsrfCookie(request.cookies);
  if (!csrfTokensMatch(header, cookie)) {
    return {
      ok: false,
      response: jsonError(
        400,
        "csrf_failed",
        "Missing or invalid X-CSRF-Token.",
      ),
    };
  }

  return session;
}
