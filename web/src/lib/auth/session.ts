import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

import { toSafePositiveInt } from "@/lib/api/safe-int";
import {
  COOKIE_SAME_SITE,
  SESSION_TTL_SECONDS,
  cookieSecure,
  type DashAuthConfig,
} from "./config";

export type SessionPayload = {
  /** Internal users.id — sole trust anchor after login. */
  user_id: number;
  /** Expiry unix seconds. */
  exp: number;
  /** Random session id — rotated on every login (anti-fixation). */
  sid: string;
  v: 1;
};

/** Cap hostile sid strings in forged cookies (mint uses 32 hex chars). */
export const MAX_SESSION_SID_LENGTH = 64;

/**
 * Cap forged session cookies before HMAC / JSON.parse.
 * Minted tokens are well under 256 chars (body + sig).
 */
export const MAX_SESSION_TOKEN_LENGTH = 512;

function b64url(buf: Buffer | string): string {
  const b = typeof buf === "string" ? Buffer.from(buf, "utf8") : buf;
  return b.toString("base64url");
}

function sign(data: string, secret: string): string {
  return createHmac("sha256", secret).update(data).digest("base64url");
}

export function mintSessionToken(
  userId: number,
  secret: string,
  ttlSeconds: number = SESSION_TTL_SECONDS,
): { token: string; payload: SessionPayload } {
  // Fail closed — float / ≤0 / unsafe ids must not mint a signed session.
  if (!Number.isSafeInteger(userId) || userId <= 0) {
    throw new Error("userId must be a positive SafeInteger");
  }
  // Fail closed — NaN/±Inf/≤0 TTL used to mint exp that skews verify.
  if (!Number.isSafeInteger(ttlSeconds) || ttlSeconds <= 0) {
    throw new Error("ttlSeconds must be a positive SafeInteger");
  }
  const payload: SessionPayload = {
    user_id: userId,
    exp: Math.floor(Date.now() / 1000) + ttlSeconds,
    sid: randomBytes(16).toString("hex"),
    v: 1,
  };
  const body = b64url(JSON.stringify(payload));
  const token = `${body}.${sign(body, secret)}`;
  return { token, payload };
}

export function verifySessionToken(
  token: unknown,
  secret: unknown,
): SessionPayload | null {
  // Fail closed — non-strings used to throw on ``.split`` / HMAC update
  // (parity csrfTokensMatch typeof guard) instead of a clean auth reject.
  if (typeof token !== "string" || typeof secret !== "string") return null;
  // Fail closed — overlong forged cookies must not burn HMAC / JSON.parse.
  if (!token || token.length > MAX_SESSION_TOKEN_LENGTH) return null;
  if (!secret) return null;
  const parts = token.split(".");
  if (parts.length !== 2) return null;
  const [body, sig] = parts;
  if (!body || !sig) return null;
  // Cap parts individually — a short total can still hide a huge body segment
  // if the other side is empty (already rejected) or tiny.
  if (body.length > MAX_SESSION_TOKEN_LENGTH || sig.length > 128) return null;

  const expected = sign(body, secret);
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;

  try {
    const json = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
    if (json?.v !== 1) return null;
    // Digits-only SafeInteger — reject float / oversized aliases.
    const user_id = toSafePositiveInt(json.user_id);
    if (user_id == null) return null;
    // Unix seconds must be SafeInteger — float exp used to skew expiry checks.
    if (typeof json.exp !== "number" || !Number.isSafeInteger(json.exp)) {
      return null;
    }
    if (typeof json.sid !== "string" || !json.sid) return null;
    if (json.sid.length > MAX_SESSION_SID_LENGTH) return null;
    // Mint emits hex; reject control / non-hex forged sid bodies.
    if (!/^[a-f0-9]+$/i.test(json.sid)) return null;
    if (json.exp < Math.floor(Date.now() / 1000)) return null;
    return { user_id, exp: json.exp, sid: json.sid, v: 1 };
  } catch {
    return null;
  }
}

export function mintCsrfToken(): string {
  return randomBytes(32).toString("base64url");
}

export function sessionCookieOptions(cfg: DashAuthConfig) {
  void cfg;
  return {
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: COOKIE_SAME_SITE,
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  };
}

export function csrfCookieOptions() {
  return {
    httpOnly: false,
    secure: cookieSecure(),
    sameSite: COOKIE_SAME_SITE,
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  };
}

/** Clear attrs must match set (Secure/SameSite/Path) or browsers keep the cookie. */
export function clearAuthCookieOptions(httpOnly: boolean) {
  return {
    httpOnly,
    secure: cookieSecure(),
    sameSite: COOKIE_SAME_SITE,
    path: "/",
    maxAge: 0,
    expires: new Date(0),
  };
}
