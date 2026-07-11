import type { NextRequest } from "next/server";

import { CSRF_COOKIE, SESSION_COOKIE } from "@/lib/auth/config";
import { jsonOk } from "@/lib/auth/errors";
import { requireSessionAndCsrf } from "@/lib/auth/guard";

export const runtime = "nodejs";

/**
 * POST /api/v1/auth/logout — requires valid session + X-CSRF-Token (no exemption).
 * Clears session and CSRF cookies.
 */
export async function POST(request: NextRequest) {
  const gated = requireSessionAndCsrf(request);
  if (!gated.ok) return gated.response;

  const res = jsonOk({ ok: true });
  const secure = process.env.NODE_ENV === "production";
  const clear = {
    httpOnly: true,
    secure,
    sameSite: "lax" as const,
    path: "/",
    maxAge: 0,
  };
  res.cookies.set(SESSION_COOKIE, "", { ...clear, httpOnly: true });
  res.cookies.set(CSRF_COOKIE, "", { ...clear, httpOnly: false });
  return res;
}
