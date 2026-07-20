import { timingSafeEqual } from "node:crypto";

import { CSRF_COOKIE, MAX_CSRF_TOKEN_LENGTH } from "./config";

/** Header clients must send on mutating /api/v1 requests (except login). */
export const CSRF_HEADER = "x-csrf-token";

/** Re-export — server callers may import from csrf or config. */
export { MAX_CSRF_TOKEN_LENGTH };

/**
 * Double-submit CSRF: `X-CSRF-Token` must equal the non-HttpOnly `koel_csrf` cookie.
 * Login (`POST /auth/demo`) is exempt; logout and all other mutations are not.
 * Returns false when either side is missing or when header ≠ cookie (length or value).
 */
export function csrfTokensMatch(
  headerToken: string | null,
  cookieToken: string | undefined,
): boolean {
  // Fail closed — non-strings used to hit Buffer.from(number) (allocates
  // a zero-filled buffer of that size) instead of a clean CSRF reject.
  if (typeof headerToken !== "string" || typeof cookieToken !== "string") {
    return false;
  }
  if (!headerToken || !cookieToken) return false;
  // Fail closed — multi-MB forged tokens must not allocate / compare.
  if (
    headerToken.length > MAX_CSRF_TOKEN_LENGTH ||
    cookieToken.length > MAX_CSRF_TOKEN_LENGTH
  ) {
    return false;
  }
  const a = Buffer.from(headerToken);
  const b = Buffer.from(cookieToken);
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

export function readCsrfCookie(
  cookies: { get: (name: string) => { value: string } | undefined },
): string | undefined {
  const raw = cookies.get(CSRF_COOKIE)?.value;
  // Fail closed — non-string / multi-MB forged cookies must not compare.
  if (typeof raw !== "string") return undefined;
  if (raw.length > MAX_CSRF_TOKEN_LENGTH) return undefined;
  return raw;
}
