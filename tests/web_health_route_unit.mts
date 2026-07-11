/**
 * E12-Q01 — health route regression harness.
 *
 * Invoked from web/ (cwd + module root) so `next` resolves:
 *   pytest tests/test_web_route_regressions.py
 */
import { NextRequest } from "next/server";

import { GET as healthGet } from "./src/app/api/v1/health/route.ts";
import { SESSION_COOKIE } from "./src/lib/auth/config.ts";
import { mintSessionToken } from "./src/lib/auth/session.ts";

const SECRET = "web-health-route-unit-secret-not-for-prod";

type HealthBody = {
  status?: string;
  db_ok?: boolean;
  poller?: {
    last_tick_ok?: boolean;
    price_poll_ok?: boolean;
    disclosure_poll_ok?: boolean;
    last_error?: string | null;
    watched_missing?: string[];
  } | null;
};

function fail(msg: string): never {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) fail(msg);
}

function makeRequest(): NextRequest {
  const { token } = mintSessionToken(42, SECRET);
  return new NextRequest("http://127.0.0.1/api/v1/health", {
    method: "GET",
    headers: { cookie: `${SESSION_COOKIE}=${token}` },
  });
}

function installDbPool(): string[] {
  process.env.DATABASE_URL = "postgres://unit.test/chime";
  const queries: string[] = [];
  (globalThis as typeof globalThis & { __chimePgPool?: unknown }).__chimePgPool = {
    query: async (sql: string) => {
      queries.push(sql);
      if (sql.includes("SELECT 1")) return { rows: [] };
      if (sql.includes("MAX(ts)")) return { rows: [{ max_ts: null }] };
      throw new Error(`unexpected query: ${sql}`);
    },
  };
  return queries;
}

async function readBody(res: Response): Promise<HealthBody> {
  return (await res.json()) as HealthBody;
}

async function testWatchedMissingDegradesRoute(): Promise<void> {
  const queries = installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  process.env.HEALTH_URL = "http://poller.local/health";

  const originalFetch = globalThis.fetch;
  const seenUrls: string[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    seenUrls.push(url);
    assert(url === process.env.HEALTH_URL, `unexpected health fetch URL ${url}`);
    assert(!url.includes("cse.lk"), "health route must not fetch cse.lk");
    return new Response(
      JSON.stringify({
        started_at: "2026-07-11T00:00:00.000Z",
        last_tick_at: "2026-07-11T04:30:00.000Z",
        last_tick_ok: true,
        price_poll_ok: true,
        disclosure_poll_ok: true,
        last_error: null,
        watched_missing: ["COMB.N0000"],
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }) as typeof fetch;

  try {
    const res = await healthGet(makeRequest());
    const body = await readBody(res);
    assert(res.status === 503, `watched_missing should return 503, got ${res.status}`);
    assert(body.status === "degraded", `expected degraded, got ${body.status}`);
    assert(body.db_ok === true, "fake DB should be healthy");
    assert(body.poller?.last_tick_ok === true, "tick remains ok in payload");
    assert(
      body.poller?.watched_missing?.[0] === "COMB.N0000",
      "watched_missing forwarded",
    );
    assert(seenUrls.length === 1, `expected one health fetch, got ${seenUrls.length}`);
    assert(queries.length === 2, `expected two DB queries, got ${queries.length}`);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

async function testUnreachableHealthUrlDegradesRoute(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  process.env.HEALTH_URL = "http://poller.local/unreachable";

  const originalFetch = globalThis.fetch;
  const seenUrls: string[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    seenUrls.push(url);
    assert(url === process.env.HEALTH_URL, `unexpected health fetch URL ${url}`);
    throw new Error("poller unavailable");
  }) as typeof fetch;

  try {
    const res = await healthGet(makeRequest());
    const body = await readBody(res);
    assert(res.status === 503, `unreachable HEALTH_URL should return 503, got ${res.status}`);
    assert(body.status === "degraded", `expected degraded, got ${body.status}`);
    assert(body.db_ok === true, "fake DB should be healthy");
    assert(body.poller?.last_tick_ok === false, "unreachable poller marks tick false");
    assert(
      body.poller?.last_error === "health_url_unreachable",
      `expected health_url_unreachable, got ${body.poller?.last_error}`,
    );
    assert(seenUrls.length === 1, `expected one health fetch, got ${seenUrls.length}`);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

async function main(): Promise<void> {
  await testWatchedMissingDegradesRoute();
  await testUnreachableHealthUrlDegradesRoute();
  console.log("WEB_HEALTH_ROUTE_UNIT_OK");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
