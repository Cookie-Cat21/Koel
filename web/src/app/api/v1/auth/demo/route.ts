import { NextResponse } from "next/server";

import { CSRF_COOKIE, getDashAuthConfig, SESSION_COOKIE } from "@/lib/auth/config";
import { jsonError } from "@/lib/auth/errors";
import {
  csrfCookieOptions,
  mintCsrfToken,
  mintSessionToken,
  sessionCookieOptions,
} from "@/lib/auth/session";
import { ensureUser } from "@/lib/db";

export const runtime = "nodejs";

type DemoBody = {
  telegram_id?: unknown;
};

export async function POST(request: Request) {
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

  if (cfg.allowlist.size === 0) {
    return jsonError(
      403,
      "telegram_id_not_allowlisted",
      "Demo allowlist is empty.",
    );
  }

  let body: DemoBody;
  try {
    body = (await request.json()) as DemoBody;
  } catch {
    return jsonError(400, "validation_error", "Invalid JSON body.");
  }

  const rawId = body.telegram_id;
  if (
    typeof rawId !== "number" ||
    !Number.isSafeInteger(rawId) ||
    rawId <= 0
  ) {
    return jsonError(
      400,
      "validation_error",
      "telegram_id must be a positive integer.",
    );
  }

  if (!cfg.allowlist.has(rawId)) {
    return jsonError(
      403,
      "telegram_id_not_allowlisted",
      "telegram_id is not on the demo allowlist.",
    );
  }

  let userId: number;
  try {
    userId = await ensureUser(rawId);
  } catch (err) {
    console.error("demo auth ensure_user failed", err);
    return jsonError(
      503,
      "degraded",
      "Database unavailable; cannot resolve user.",
    );
  }

  const { token } = mintSessionToken(userId, cfg.sessionSecret);
  const csrf = mintCsrfToken();

  const res = NextResponse.json(
    {
      user: { id: userId, telegram_id: rawId },
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
