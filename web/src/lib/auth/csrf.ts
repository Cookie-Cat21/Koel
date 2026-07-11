import { timingSafeEqual } from "node:crypto";

import { CSRF_COOKIE } from "./config";

/** Header clients must send on mutating /api/v1 requests (except login). */
export const CSRF_HEADER = "x-csrf-token";

/**
 * Double-submit CSRF: `X-CSRF-Token` must equal the non-HttpOnly `chime_csrf` cookie.
 * Login (`POST /auth/demo`) is exempt; logout and all other mutations are not.
 */
export function csrfTokensMatch(
  headerToken: string | null,
  cookieToken: string | undefined,
): boolean {
  if (!headerToken || !cookieToken) return false;
  const a = Buffer.from(headerToken);
  const b = Buffer.from(cookieToken);
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

export function readCsrfCookie(
  cookies: { get: (name: string) => { value: string } | undefined },
): string | undefined {
  return cookies.get(CSRF_COOKIE)?.value;
}
