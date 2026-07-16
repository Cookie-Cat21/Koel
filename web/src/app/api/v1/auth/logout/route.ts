import type { NextRequest } from "next/server";

import { CSRF_COOKIE, SESSION_COOKIE } from "@/lib/auth/config";
import { jsonOk } from "@/lib/auth/errors";
import { requireSessionAndCsrf } from "@/lib/auth/guard";
import { clearAuthCookieOptions } from "@/lib/auth/session";

export const runtime = "nodejs";

/**
 * POST /api/v1/auth/logout — requires valid session + X-CSRF-Token (no exemption).
 * Clears session and CSRF cookies.
 */
export async function POST(request: NextRequest) {
  const gated = await requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

  const res = jsonOk({ ok: true });
  res.cookies.set(SESSION_COOKIE, "", clearAuthCookieOptions(true));
  res.cookies.set(CSRF_COOKIE, "", clearAuthCookieOptions(false));
  return res;
}
