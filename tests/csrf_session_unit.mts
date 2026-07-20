/**
 * E9-Q01 / E9-Q02 / E10-Q01 / E10-Q02 / E10-Q03 — unit harness for dash
 * CSRF + session guards (and logout cookie clear).
 *
 * Invoked from web/ (cwd + module root) so `next` resolves:
 *   pytest tests/test_csrf_session_contract.py
 *   # or: cp tests/csrf_session_unit.mts web/.csrf_session_unit.mts && cd web && npx tsx .csrf_session_unit.mts
 *
 * Exercises real exports (csrfTokensMatch, requireSessionAndCsrf) with
 * NextRequest — no live server required. Logout happy-path is unit-mocked
 * via the route handler (RUN_WEB live optional elsewhere).
 */
import { NextRequest } from "next/server";

import { POST as logoutPost } from "./src/app/api/v1/auth/logout/route.ts";
import { CSRF_COOKIE, SESSION_COOKIE } from "./src/lib/auth/config.ts";
import { csrfTokensMatch } from "./src/lib/auth/csrf.ts";
import { requireSessionAndCsrf } from "./src/lib/auth/guard.ts";
import { mintCsrfToken, mintSessionToken } from "./src/lib/auth/session.ts";

const SECRET = "csrf-session-unit-secret-not-for-prod";

function fail(msg: string): never {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) fail(msg);
}

async function bodyOf(
  res: Response,
): Promise<{ error?: { code?: string }; ok?: boolean }> {
  return (await res.json()) as { error?: { code?: string }; ok?: boolean };
}

async function main(): Promise<void> {
  process.env.DASH_SESSION_SECRET = SECRET;
  // Skip dash_sessions revoke lookup — this harness has no Postgres.
  process.env.DASH_SESSION_REVOKE_CHECK = "0";

  // --- csrfTokensMatch (exported helper) ---
  assert(csrfTokensMatch("same-token", "same-token") === true, "match equal");
  assert(csrfTokensMatch(null, "x") === false, "null header");
  assert(csrfTokensMatch("x", undefined) === false, "missing cookie");
  assert(csrfTokensMatch("ab", "abc") === false, "length mismatch");
  assert(csrfTokensMatch("token-a", "token-b") === false, "value mismatch");

  const { token: session } = mintSessionToken(42, SECRET);
  const csrf = mintCsrfToken();
  const otherCsrf = mintCsrfToken();
  assert(csrf !== otherCsrf, "minted CSRF tokens must differ");

  // E9-Q01: session present, CSRF missing → 400 csrf_failed (logout path)
  {
    const req = new NextRequest("http://127.0.0.1/api/v1/auth/logout", {
      method: "POST",
      headers: { cookie: `koel_session=${session}` },
    });
    const gated = await requireSessionAndCsrf(req);
    assert(!gated.ok, "logout without CSRF must fail");
    assert(gated.response.status === 400, `expected 400 got ${gated.response.status}`);
    const body = await bodyOf(gated.response);
    assert(body.error?.code === "csrf_failed", `expected csrf_failed got ${body.error?.code}`);
  }

  // E9-Q01 variant: session + cookie but no header → csrf_failed
  {
    const req = new NextRequest("http://127.0.0.1/api/v1/auth/logout", {
      method: "POST",
      headers: { cookie: `koel_session=${session}; koel_csrf=${csrf}` },
    });
    const gated = await requireSessionAndCsrf(req);
    assert(!gated.ok, "logout without header must fail");
    assert(gated.response.status === 400, `expected 400 got ${gated.response.status}`);
    const body = await bodyOf(gated.response);
    assert(body.error?.code === "csrf_failed", `expected csrf_failed got ${body.error?.code}`);
  }

  // E10-Q01: session + CSRF cookie present, header ≠ cookie → 400 csrf_failed
  {
    const req = new NextRequest("http://127.0.0.1/api/v1/auth/logout", {
      method: "POST",
      headers: {
        cookie: `koel_session=${session}; koel_csrf=${csrf}`,
        "x-csrf-token": otherCsrf,
      },
    });
    const gated = await requireSessionAndCsrf(req);
    assert(!gated.ok, "header≠cookie CSRF must fail");
    assert(gated.response.status === 400, `expected 400 got ${gated.response.status}`);
    const body = await bodyOf(gated.response);
    assert(body.error?.code === "csrf_failed", `expected csrf_failed got ${body.error?.code}`);
  }

  // E9-Q02: mutate without session → 401 unauthorized
  {
    const req = new NextRequest("http://127.0.0.1/api/v1/watchlist", {
      method: "POST",
      headers: { "content-type": "application/json" },
    });
    const gated = await requireSessionAndCsrf(req);
    assert(!gated.ok, "mutate without session must fail");
    assert(gated.response.status === 401, `expected 401 got ${gated.response.status}`);
    const body = await bodyOf(gated.response);
    assert(body.error?.code === "unauthorized", `expected unauthorized got ${body.error?.code}`);
  }

  // E10-Q03: missing session → 401 before CSRF (even if CSRF would also fail)
  {
    const req = new NextRequest("http://127.0.0.1/api/v1/watchlist", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        cookie: `koel_csrf=${csrf}`,
        "x-csrf-token": otherCsrf,
      },
    });
    const gated = await requireSessionAndCsrf(req);
    assert(!gated.ok, "no session must fail even with CSRF material");
    assert(
      gated.response.status === 401,
      `expected 401 before CSRF got ${gated.response.status}`,
    );
    const body = await bodyOf(gated.response);
    assert(
      body.error?.code === "unauthorized",
      `expected unauthorized (not csrf_failed) got ${body.error?.code}`,
    );
  }

  // Happy path: session + matching CSRF (guard)
  {
    const req = new NextRequest("http://127.0.0.1/api/v1/auth/logout", {
      method: "POST",
      headers: {
        cookie: `koel_session=${session}; koel_csrf=${csrf}`,
        "x-csrf-token": csrf,
      },
    });
    const gated = await requireSessionAndCsrf(req);
    assert(gated.ok, "matching CSRF must pass");
    assert(gated.session.user_id === 42, "user_id from session");
  }

  // E10-Q02: logout happy-path clears session + CSRF cookies (unit mock of handler)
  {
    const req = new NextRequest("http://127.0.0.1/api/v1/auth/logout", {
      method: "POST",
      headers: {
        cookie: `koel_session=${session}; koel_csrf=${csrf}`,
        "x-csrf-token": csrf,
      },
    });
    const res = await logoutPost(req);
    assert(res.status === 200, `logout expected 200 got ${res.status}`);
    const body = await bodyOf(res);
    assert(body.ok === true, "logout body ok");
    const clearedSession = res.cookies.get(SESSION_COOKIE);
    const clearedCsrf = res.cookies.get(CSRF_COOKIE);
    assert(clearedSession !== undefined, "Set-Cookie koel_session present");
    assert(clearedCsrf !== undefined, "Set-Cookie koel_csrf present");
    assert(clearedSession.value === "", `session cookie cleared, got ${clearedSession.value}`);
    assert(clearedCsrf.value === "", `csrf cookie cleared, got ${clearedCsrf.value}`);
  }

  console.log("CSRF_SESSION_UNIT_OK");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
