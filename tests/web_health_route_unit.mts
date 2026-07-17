/**
 * E12-Q01 — health route regression harness.
 *
 * Invoked from web/ (cwd + module root) so `next` resolves:
 *   pytest tests/test_web_route_regressions.py
 */
import { NextRequest } from "next/server";

import {
  GET as healthGet,
  HEALTH_PROXY_TIMEOUT_MS_DEFAULT,
  healthProxyTimeoutMs,
} from "./src/app/api/v1/health/route.ts";
import { SESSION_COOKIE } from "./src/lib/auth/config.ts";
import { mintSessionToken } from "./src/lib/auth/session.ts";

const SECRET = "web-health-route-unit-secret-not-for-prod";

type HealthBody = {
  status?: string;
  db_ok?: boolean;
  delivery?: {
    delivered_24h?: number;
    retrying?: number;
    dead_lettered?: number;
  };
  retention?: {
    snapshot_retention_days?: number;
  };
  poller?: {
    last_tick_ok?: boolean;
    price_poll_ok?: boolean;
    disclosure_poll_ok?: boolean;
    last_error?: string | null;
    watched_missing?: string[];
    brief_queue?: {
      pending_briefs?: number;
      pdf_enrich?: {
        in_flight_tasks?: number;
        last_batch_size?: number;
        batches_started?: number;
      };
    };
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

/** True for the three core health queries (liveness, snapshot age, delivery). */
function isBaseHealthQuery(sql: string): boolean {
  return (
    sql.includes("SELECT 1") ||
    sql.includes("FROM price_snapshots") ||
    sql.includes("FROM alert_log")
  );
}

function installDbPool(): string[] {
  process.env.DATABASE_URL = "postgres://unit.test/chime";
  const queries: string[] = [];
  (globalThis as typeof globalThis & { __chimePgPool?: unknown }).__chimePgPool = {
    query: async (sql: string) => {
      queries.push(sql);
      if (sql.includes("SELECT 1")) return { rows: [] };
      // ML health block (best-effort, each query individually try/caught in
      // the route) — answer with empty/zero shapes so the block stays quiet.
      if (sql.includes("FROM model_registry")) return { rows: [], rowCount: 0 };
      if (sql.includes("FROM forecast_outcomes")) return { rows: [], rowCount: 0 };
      if (sql.includes("FROM market_daily_summary")) return { rows: [{ n: 0 }] };
      if (sql.includes("FROM order_book_snapshots")) {
        return { rows: [{ n: 0, mx: null }] };
      }
      if (sql.includes("FROM forecast_points")) {
        return { rows: [{ as_of: null, spoke: 0 }] };
      }
      if (sql.includes("MAX(ts)")) return { rows: [{ max_ts: null }] };
      if (sql.includes("FROM alert_log")) {
        return {
          rows: [{ delivered_24h: 2, retrying: 1, dead_lettered: 3 }],
        };
      }
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
  process.env.HEALTH_URL = "http://127.0.0.1:8080/health";

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
    assert(body.delivery?.delivered_24h === 2, "delivery delivered_24h forwarded");
    assert(body.delivery?.retrying === 1, "delivery retrying forwarded");
    assert(body.delivery?.dead_lettered === 3, "delivery dead_lettered forwarded");
    assert(
      body.retention?.snapshot_retention_days === 0,
      "retention default forwarded",
    );
    assert(seenUrls.length === 1, `expected one health fetch, got ${seenUrls.length}`);
    const baseQueries = queries.filter(isBaseHealthQuery);
    assert(
      baseQueries.length === 3,
      `expected three core DB queries, got ${baseQueries.length}`,
    );
    // Anything beyond core must be the allowlisted ML-health block — the
    // fake pool throws on unknown SQL, so growth here fails loudly.
    assert(
      queries.length <= 8,
      `unexpected extra DB queries (${queries.length} total)`,
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
}

async function testUnreachableHealthUrlDegradesRoute(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  process.env.HEALTH_URL = "http://127.0.0.1:8080/unreachable";

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

async function testHealthProxyTimeoutAbortsAndDegrades(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  process.env.HEALTH_URL = "http://127.0.0.1:8080/slow";
  process.env.HEALTH_PROXY_TIMEOUT_MS = "40";
  assert(healthProxyTimeoutMs() === 40, "test timeout env should parse to 40ms");

  const originalFetch = globalThis.fetch;
  let sawAbort = false;
  globalThis.fetch = ((
    _input: RequestInfo | URL,
    init?: RequestInit,
  ): Promise<Response> => {
    const signal = init?.signal;
    return new Promise((_resolve, reject) => {
      const fail = () => {
        sawAbort = true;
        reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
      };
      if (signal?.aborted) {
        fail();
        return;
      }
      signal?.addEventListener("abort", fail, { once: true });
    });
  }) as typeof fetch;

  const started = Date.now();
  try {
    const res = await healthGet(makeRequest());
    const body = await readBody(res);
    const elapsed = Date.now() - started;
    assert(res.status === 503, `timeout proxy should return 503, got ${res.status}`);
    assert(body.status === "degraded", `expected degraded, got ${body.status}`);
    assert(
      body.poller?.last_error === "health_url_unreachable",
      `expected health_url_unreachable, got ${body.poller?.last_error}`,
    );
    assert(sawAbort, "fetch mock must observe AbortSignal abort");
    assert(elapsed < 1500, `proxy timeout should be fast, took ${elapsed}ms`);
  } finally {
    globalThis.fetch = originalFetch;
    delete process.env.HEALTH_PROXY_TIMEOUT_MS;
  }

  process.env.HEALTH_PROXY_TIMEOUT_MS = "0";
  assert(
    healthProxyTimeoutMs() === HEALTH_PROXY_TIMEOUT_MS_DEFAULT,
    "non-positive HEALTH_PROXY_TIMEOUT_MS must fail closed to default",
  );
  process.env.HEALTH_PROXY_TIMEOUT_MS = "nan";
  assert(
    healthProxyTimeoutMs() === HEALTH_PROXY_TIMEOUT_MS_DEFAULT,
    "invalid HEALTH_PROXY_TIMEOUT_MS must fail closed to default",
  );
  delete process.env.HEALTH_PROXY_TIMEOUT_MS;
}

async function testBriefQueueForwardedWithoutDegrading(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  process.env.HEALTH_URL = "http://127.0.0.1:8080/health";

  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    assert(url === process.env.HEALTH_URL, `unexpected health fetch URL ${url}`);
    return new Response(
      JSON.stringify({
        started_at: "2026-07-11T00:00:00.000Z",
        last_tick_at: "2026-07-11T04:30:00.000Z",
        last_tick_ok: true,
        price_poll_ok: true,
        disclosure_poll_ok: true,
        last_error: null,
        watched_missing: [],
        brief_queue: {
          pending_briefs: 4,
          pdf_enrich: {
            in_flight_tasks: 1,
            last_batch_size: 3,
            batches_started: 2,
          },
        },
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }) as typeof fetch;

  try {
    const res = await healthGet(makeRequest());
    const body = await readBody(res);
    assert(res.status === 200, `brief_queue hint must not degrade, got ${res.status}`);
    assert(body.status === "ok", `expected ok, got ${body.status}`);
    assert(body.poller?.brief_queue?.pending_briefs === 4, "pending_briefs forwarded");
    assert(
      body.poller?.brief_queue?.pdf_enrich?.in_flight_tasks === 1,
      "pdf_enrich.in_flight_tasks forwarded",
    );
    assert(
      body.poller?.brief_queue?.pdf_enrich?.last_batch_size === 3,
      "pdf_enrich.last_batch_size forwarded",
    );
    assert(
      body.poller?.brief_queue?.pdf_enrich?.batches_started === 2,
      "pdf_enrich.batches_started forwarded",
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
}

async function testNestedPollerCannotOverwriteSanitizedFields(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  process.env.HEALTH_URL = "http://127.0.0.1:8080/health";

  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    assert(url === process.env.HEALTH_URL, `unexpected health fetch URL ${url}`);
    return new Response(
      JSON.stringify({
        started_at: "2026-07-11T00:00:00.000Z",
        last_tick_ok: true,
        price_poll_ok: true,
        disclosure_poll_ok: true,
        last_error: null,
        watched_missing: [],
        // Hostile nested shape used to raw-spread and clobber typed fields.
        poller: {
          last_tick_ok: "yes",
          price_poll_ok: "nope",
          watched_missing: [
            1,
            null,
            "COMB\u0000.N0000",
            "X".repeat(2000),
            "JKH.N0000",
          ],
          last_error: { nested: true },
          brief_queue: { pending_briefs: Number.NaN },
        },
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }) as typeof fetch;

  try {
    const res = await healthGet(makeRequest());
    const body = await readBody(res);
    // Top-level booleans must survive — nested non-booleans must not overwrite.
    assert(body.poller?.last_tick_ok === true, "nested string must not clobber last_tick_ok");
    assert(body.poller?.price_poll_ok === true, "nested string must not clobber price_poll_ok");
    assert(body.poller?.disclosure_poll_ok === true, "disclosure_poll_ok preserved");
    // Only CSE SYMBOL_RE kept — controls / oversize / non-tickers dropped.
    const missing = body.poller?.watched_missing ?? [];
    assert(missing.length === 1, `expected 1 SYMBOL_RE symbol, got ${missing.length}`);
    assert(missing[0] === "JKH.N0000", `expected JKH.N0000, got ${missing[0]}`);
    assert(body.poller?.last_error === null, "nested object last_error must not clobber null");
    assert(body.poller?.brief_queue === undefined, "NaN brief_queue must be omitted");
    // Cleaned missing still degrades ops status.
    assert(res.status === 503, `cleaned watched_missing should degrade, got ${res.status}`);
    assert(body.status === "degraded", `expected degraded, got ${body.status}`);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

async function testAllJunkNestedWatchedMissingDoesNotClearTop(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  process.env.HEALTH_URL = "http://127.0.0.1:8080/health";

  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    assert(url === process.env.HEALTH_URL, `unexpected health fetch URL ${url}`);
    return new Response(
      JSON.stringify({
        started_at: "2026-07-11T00:00:00.000Z",
        last_tick_ok: true,
        price_poll_ok: true,
        disclosure_poll_ok: true,
        last_error: null,
        watched_missing: ["COMB.N0000"],
        poller: {
          watched_missing: [1, null, "X".repeat(2000)],
        },
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }) as typeof fetch;

  try {
    const res = await healthGet(makeRequest());
    const body = await readBody(res);
    const missing = body.poller?.watched_missing ?? [];
    assert(
      missing.length === 1 && missing[0] === "COMB.N0000",
      `all-junk nested must not clear top watched_missing, got ${JSON.stringify(missing)}`,
    );
    assert(res.status === 503, `top watched_missing should degrade, got ${res.status}`);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

async function testNonLoopbackHealthUrlRejectedWithoutFetch(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  process.env.HEALTH_URL = "http://evil.example/metadata";

  const originalFetch = globalThis.fetch;
  let fetchCalls = 0;
  globalThis.fetch = (async () => {
    fetchCalls += 1;
    fail("non-loopback HEALTH_URL must not fetch");
  }) as typeof fetch;

  try {
    const res = await healthGet(makeRequest());
    const body = await readBody(res);
    assert(res.status === 503, `rejected HEALTH_URL should return 503, got ${res.status}`);
    assert(body.status === "degraded", `expected degraded, got ${body.status}`);
    assert(body.db_ok === true, "fake DB should be healthy");
    assert(body.poller?.last_tick_ok === false, "rejected URL marks tick false");
    assert(
      body.poller?.last_error === "health_url_unreachable",
      `expected health_url_unreachable, got ${body.poller?.last_error}`,
    );
    assert(fetchCalls === 0, `expected zero fetches, got ${fetchCalls}`);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

async function main(): Promise<void> {
  await testWatchedMissingDegradesRoute();
  await testUnreachableHealthUrlDegradesRoute();
  await testNonLoopbackHealthUrlRejectedWithoutFetch();
  await testHealthProxyTimeoutAbortsAndDegrades();
  await testBriefQueueForwardedWithoutDegrading();
  await testNestedPollerCannotOverwriteSanitizedFields();
  await testAllJunkNestedWatchedMissingDoesNotClearTop();
  console.log("WEB_HEALTH_ROUTE_UNIT_OK");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
