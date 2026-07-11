import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

import { SESSION_TTL_SECONDS, type DashAuthConfig } from "./config";

export type SessionPayload = {
  /** Internal users.id — sole trust anchor after login. */
  user_id: number;
  /** Expiry unix seconds. */
  exp: number;
  /** Random session id — rotated on every login (anti-fixation). */
  sid: string;
  v: 1;
};

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
  token: string,
  secret: string,
): SessionPayload | null {
  const parts = token.split(".");
  if (parts.length !== 2) return null;
  const [body, sig] = parts;
  if (!body || !sig) return null;

  const expected = sign(body, secret);
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;

  try {
    const json = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
    if (
      json?.v !== 1 ||
      typeof json.user_id !== "number" ||
      !Number.isSafeInteger(json.user_id) ||
      json.user_id <= 0 ||
      typeof json.exp !== "number" ||
      typeof json.sid !== "string"
    ) {
      return null;
    }
    if (json.exp < Math.floor(Date.now() / 1000)) return null;
    return json as SessionPayload;
  } catch {
    return null;
  }
}

export function mintCsrfToken(): string {
  return randomBytes(32).toString("base64url");
}

export function sessionCookieOptions(cfg: DashAuthConfig) {
  void cfg;
  const secure = process.env.NODE_ENV === "production";
  return {
    httpOnly: true,
    secure,
    sameSite: "lax" as const,
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  };
}

export function csrfCookieOptions() {
  const secure = process.env.NODE_ENV === "production";
  return {
    httpOnly: false,
    secure,
    sameSite: "lax" as const,
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  };
}
