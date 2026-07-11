import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getDashAuthConfig, SESSION_COOKIE } from "./config";
import { type SessionPayload, verifySessionToken } from "./session";

/** Require a signed session for App Router pages; redirect to /login if missing. */
export async function requirePageSession(): Promise<SessionPayload> {
  const cfg = getDashAuthConfig();
  const jar = await cookies();
  const raw = jar.get(SESSION_COOKIE)?.value;
  const session =
    raw && cfg.sessionSecret
      ? verifySessionToken(raw, cfg.sessionSecret)
      : null;
  if (!session) {
    redirect("/login");
  }
  return session;
}
