import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";

import { readJsonBody } from "@/lib/api/read-json-body";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { CSRF_COOKIE, getDashAuthConfig, SESSION_COOKIE } from "@/lib/auth/config";
import { jsonError } from "@/lib/auth/errors";
import {
  clientIpFromRequest,
  hitRateLimit,
} from "@/lib/auth/rate-limit";
import {
  csrfCookieOptions,
  mintCsrfToken,
  mintSessionToken,
  sessionCookieOptions,
} from "@/lib/auth/session";
import { ensureUser, recordDashSession } from "@/lib/db";

export const runtime = "nodejs";

/** S-04: telegram login — 20 attempts / minute / IP (best-effort in-memory). */
const TELEGRAM_AUTH_RATE_LIMIT = 20;
const TELEGRAM_AUTH_RATE_WINDOW_MS = 60_000;

const TELEGRAM_LOGIN_MAX_AGE_SECONDS = 24 * 60 * 60;
const TELEGRAM_LOGIN_CLOCK_SKEW_SECONDS = 5 * 60;
const HASH_RE = /^[a-f0-9]{64}$/i;
const CTRL_LINE_RE = /[\r\n]/;

async function readTelegramPayload(
  request: Request,
): Promise<
  | { ok: true; payload: Record<string, string> }
  | { ok: false; response: NextResponse }
> {
  const contentType = request.headers.get("content-type") ?? "";
  if (
    contentType.includes("application/x-www-form-urlencoded") ||
    contentType.includes("multipart/form-data")
  ) {
    try {
      const form = await request.formData();
      const payload: Record<string, string> = {};
      for (const [key, value] of form.entries()) {
        if (typeof value !== "string") {
          return {
            ok: false,
            response: jsonError(400, "validation_error", "Invalid Telegram payload."),
          };
        }
        payload[key] = value;
      }
      return { ok: true, payload };
    } catch {
      return {
        ok: false,
        response: jsonError(400, "validation_error", "Invalid form body."),
      };
    }
  }

  const parsed = await readJsonBody(request);
  if (!parsed.ok || typeof parsed.value !== "object" || parsed.value === null) {
    return {
      ok: false,
      response: jsonError(400, "validation_error", "Invalid JSON body."),
    };
  }
  const payload: Record<string, string> = {};
  for (const [key, value] of Object.entries(
    parsed.value as Record<string, unknown>,
  )) {
    if (typeof value === "string" || typeof value === "number") {
      payload[key] = String(value);
    } else {
      return {
        ok: false,
        response: jsonError(400, "validation_error", "Invalid Telegram payload."),
      };
    }
  }
  return { ok: true, payload };
}

function verifyTelegramLogin(
  payload: Record<string, string>,
  botToken: string,
): boolean {
  const hash = payload.hash;
  if (typeof hash !== "string" || !HASH_RE.test(hash)) return false;
  const entries = Object.entries(payload)
    .filter(([key]) => key !== "hash")
    .sort(([a], [b]) => a.localeCompare(b));
  if (entries.length === 0) return false;
  for (const [key, value] of entries) {
    if (!key || CTRL_LINE_RE.test(key) || CTRL_LINE_RE.test(value)) return false;
  }
  const dataCheckString = entries.map(([key, value]) => `${key}=${value}`).join("\n");
  const secret = createHash("sha256").update(botToken).digest();
  const expected = createHmac("sha256", secret)
    .update(dataCheckString)
    .digest();
  const actual = Buffer.from(hash, "hex");
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}

export async function POST(request: Request) {
  const ip = clientIpFromRequest(request);
  const limited = hitRateLimit(`auth:telegram:${ip}`, {
    limit: TELEGRAM_AUTH_RATE_LIMIT,
    windowMs: TELEGRAM_AUTH_RATE_WINDOW_MS,
  });
  if (!limited.ok) {
    const res = jsonError(
      429,
      "rate_limited",
      "Too many sign-in attempts. Try again shortly.",
    );
    res.headers.set("Retry-After", String(limited.retryAfterSec));
    return res;
  }

  const loginFlag = process.env.DASH_TELEGRAM_LOGIN;
  if (typeof loginFlag !== "string" || loginFlag !== "1") {
    return jsonError(404, "not_found", "Telegram login is disabled.");
  }
  const tokenRaw = process.env.TELEGRAM_BOT_TOKEN;
  const botToken = typeof tokenRaw === "string" ? tokenRaw.trim() : "";
  if (!botToken) {
    return jsonError(403, "telegram_login_disabled", "Telegram login is disabled.");
  }

  const cfg = getDashAuthConfig();
  if (!cfg.sessionSecret) {
    return jsonError(
      503,
      "degraded",
      "DASH_SESSION_SECRET is not configured.",
    );
  }

  const parsed = await readTelegramPayload(request);
  if (!parsed.ok) return parsed.response;
  const payload = parsed.payload;

  const telegramId = toSafePositiveInt(payload.id);
  const authDate = toSafePositiveInt(payload.auth_date);
  if (telegramId == null || authDate == null) {
    return jsonError(403, "telegram_login_invalid", "Invalid Telegram login.");
  }
  const now = Math.floor(Date.now() / 1000);
  if (
    authDate < now - TELEGRAM_LOGIN_MAX_AGE_SECONDS ||
    authDate > now + TELEGRAM_LOGIN_CLOCK_SKEW_SECONDS
  ) {
    return jsonError(403, "telegram_login_expired", "Telegram login expired.");
  }
  if (!verifyTelegramLogin(payload, botToken)) {
    return jsonError(403, "telegram_login_invalid", "Invalid Telegram login.");
  }

  let userId: number;
  try {
    userId = await ensureUser(telegramId);
  } catch (err) {
    console.error("telegram auth ensure_user failed", err);
    return jsonError(
      503,
      "degraded",
      "Database unavailable; cannot resolve user.",
    );
  }

  const { token, payload: sessionPayload } = mintSessionToken(
    userId,
    cfg.sessionSecret,
  );
  try {
    await recordDashSession(
      userId,
      sessionPayload.sid,
      request.headers.get("user-agent"),
    );
  } catch (err) {
    console.error("telegram auth recordDashSession failed", err);
  }
  const csrf = mintCsrfToken();
  const res = NextResponse.json(
    {
      user: { id: userId, telegram_id: telegramId },
      csrf_token: csrf,
    },
    {
      status: 200,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    },
  );
  res.cookies.set(SESSION_COOKIE, token, sessionCookieOptions(cfg));
  res.cookies.set(CSRF_COOKIE, csrf, csrfCookieOptions());
  return res;
}
