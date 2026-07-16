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

/** S-04: demo auth — 20 attempts / minute / IP (best-effort in-memory). */
const DEMO_AUTH_RATE_LIMIT = 20;
const DEMO_AUTH_RATE_WINDOW_MS = 60_000;

type DemoBody = {
  telegram_id?: unknown;
};

/**
 * Parse telegram_id from JSON (SPA fetch) or form POST (no-JS fallback).
 * Form path redirects to /overview after Set-Cookie so Cloud Agent
 * previews still work if client JS is blocked mid-hydration.
 */
async function readTelegramId(
  request: Request,
): Promise<
  | { ok: true; telegramId: unknown; redirect: boolean }
  | { ok: false; response: NextResponse }
> {
  const contentType = request.headers.get("content-type") ?? "";
  const isForm =
    contentType.includes("application/x-www-form-urlencoded") ||
    contentType.includes("multipart/form-data");

  if (isForm) {
    try {
      const form = await request.formData();
      return { ok: true, telegramId: form.get("telegram_id"), redirect: true };
    } catch {
      return {
        ok: false,
        response: jsonError(400, "validation_error", "Invalid form body."),
      };
    }
  }

  const parsed = await readJsonBody(request);
  if (!parsed.ok) {
    if (parsed.reason === "too_large") {
      return {
        ok: false,
        response: jsonError(400, "validation_error", "Request body too large."),
      };
    }
    return {
      ok: false,
      response: jsonError(400, "validation_error", "Invalid JSON body."),
    };
  }
  if (typeof parsed.value !== "object" || parsed.value === null) {
    return {
      ok: false,
      response: jsonError(400, "validation_error", "Invalid JSON body."),
    };
  }
  const body = parsed.value as DemoBody;
  return { ok: true, telegramId: body.telegram_id, redirect: false };
}

function overviewRedirect(): NextResponse {
  // Relative Location keeps the Cloud Agent preview Host (never bounce to
  // http://0.0.0.0:3000/... which surfaces as "request could not be routed").
  return new NextResponse(null, {
    status: 303,
    headers: { Location: "/overview" },
  });
}

export async function POST(request: Request) {
  const ip = clientIpFromRequest(request);
  const limited = hitRateLimit(`auth:demo:${ip}`, {
    limit: DEMO_AUTH_RATE_LIMIT,
    windowMs: DEMO_AUTH_RATE_WINDOW_MS,
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

  const cfg = getDashAuthConfig();

  if (!cfg.demoAuthEnabled) {
    return jsonError(
      403,
      "demo_auth_disabled",
      "Demo authentication is disabled.",
    );
  }

  if (!cfg.sessionSecret) {
    return jsonError(
      503,
      "degraded",
      "DASH_SESSION_SECRET is not configured.",
    );
  }

  const parsed = await readTelegramId(request);
  if (!parsed.ok) {
    return parsed.response;
  }

  // Digits-only SafeInteger — Number("9…093") can alias MAX_SAFE_INTEGER and
  // pass a bare isSafeInteger gate; reject floats / sci-notation / oversized.
  const telegramId = toSafePositiveInt(parsed.telegramId);
  if (telegramId == null) {
    return jsonError(
      400,
      "validation_error",
      "telegram_id must be a positive integer.",
    );
  }

  // S-11: empty allowlist and unknown ID share one denial (no enumeration).
  if (cfg.allowlist.size === 0 || !cfg.allowlist.has(telegramId)) {
    return jsonError(
      403,
      "demo_auth_denied",
      "Demo sign-in is not available for this Telegram ID.",
    );
  }

  let userId: number;
  try {
    userId = await ensureUser(telegramId);
  } catch (err) {
    console.error("demo auth ensure_user failed", err);
    return jsonError(
      503,
      "degraded",
      "Database unavailable; cannot resolve user.",
    );
  }

  const { token, payload } = mintSessionToken(userId, cfg.sessionSecret);
  try {
    await recordDashSession(
      userId,
      payload.sid,
      request.headers.get("user-agent"),
    );
  } catch (err) {
    console.error("demo auth recordDashSession failed", err);
    // Non-fatal — cookie still works; device list may lag.
  }
  const csrf = mintCsrfToken();

  const res = parsed.redirect
    ? overviewRedirect()
    : NextResponse.json(
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
