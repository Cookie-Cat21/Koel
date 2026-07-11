/**
 * E9-Q01 / E9-Q02 — unit harness for dash CSRF + session guards.
 *
 * Invoked from web/ (cwd + module root) so `next` resolves:
 *   pytest tests/test_csrf_session_contract.py
 *   # or: cp tests/csrf_session_unit.mts web/.csrf_session_unit.mts && cd web && npx tsx .csrf_session_unit.mts
 *
 * Exercises real exports (csrfTokensMatch, requireSessionAndCsrf) with
 * NextRequest — no live server required.
 */
import { NextRequest } from "next/server";

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

async function bodyOf(res: Response): Promise<{ error?: { code?: string } }> {
  return (await res.json()) as { error?: { code?: string } };
}

async function main(): Promise<void> {
  process.env.DASH_SESSION_SECRET = SECRET;

  // --- csrfTokensMatch (exported helper) ---
  assert(csrfTokensMatch("same-token", "same-token") === true, "match equal");
  assert(csrfTokensMatch(null, "x") === false, "null header");
  assert(csrfTokensMatch("x", undefined) === false, "missing cookie");
  assert(csrfTokensMatch("ab", "abc") === false, "length mismatch");
  assert(csrfTokensMatch("token-a", "token-b") === false, "value mismatch");

  const { token: session } = mintSessionToken(42, SECRET);
  const csrf = mintCsrfToken();

  // E9-Q01: session present, CSRF missing → 400 csrf_failed (logout path)
  {
    const req = new NextRequest("http://127.0.0.1/api/v1/auth/logout", {
      method: "POST",
      headers: { cookie: `chime_session=${session}` },
    });
    const gated = requireSessionAndCsrf(req);
    assert(!gated.ok, "logout without CSRF must fail");
    assert(gated.response.status === 400, `expected 400 got ${gated.response.status}`);
    const body = await bodyOf(gated.response);
    assert(body.error?.code === "csrf_failed", `expected csrf_failed got ${body.error?.code}`);
  }

  // E9-Q01 variant: session + cookie but no header → csrf_failed
  {
    const req = new NextRequest("http://127.0.0.1/api/v1/auth/logout", {
      method: "POST",
      headers: { cookie: `chime_session=${session}; chime_csrf=${csrf}` },
    });
    const gated = requireSessionAndCsrf(req);
    assert(!gated.ok, "logout without header must fail");
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
    const gated = requireSessionAndCsrf(req);
    assert(!gated.ok, "mutate without session must fail");
    assert(gated.response.status === 401, `expected 401 got ${gated.response.status}`);
    const body = await bodyOf(gated.response);
    assert(body.error?.code === "unauthorized", `expected unauthorized got ${body.error?.code}`);
  }

  // Happy path: session + matching CSRF
  {
    const req = new NextRequest("http://127.0.0.1/api/v1/auth/logout", {
      method: "POST",
      headers: {
        cookie: `chime_session=${session}; chime_csrf=${csrf}`,
        "x-csrf-token": csrf,
      },
    });
    const gated = requireSessionAndCsrf(req);
    assert(gated.ok, "matching CSRF must pass");
    assert(gated.session.user_id === 42, "user_id from session");
  }

  console.log("CSRF_SESSION_UNIT_OK");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
