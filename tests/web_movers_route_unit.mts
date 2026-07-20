/**
 * GET /api/v1/market/movers — direction/sign filter + finite egress harness.
 *
 * Invoked from web/ (cwd + module root) so `next` resolves:
 *   pytest tests/test_web_route_regressions.py::test_market_movers_route_unit
 */
import { NextRequest } from "next/server";

import { GET as moversGet } from "./src/app/api/v1/market/movers/route.ts";
import { toFiniteNumber } from "./src/lib/api/market-browse.ts";
import { SESSION_COOKIE } from "./src/lib/auth/config.ts";
import { mintSessionToken } from "./src/lib/auth/session.ts";

const SECRET = "web-movers-route-unit-secret-not-for-prod";

type MoversBody = {
  items?: unknown[];
  direction?: string;
  limit?: number;
  error?: { code?: string; message?: string } | string;
};

type CapturedQuery = { sql: string; params: unknown[] };

function fail(msg: string): never {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) fail(msg);
}

function makeRequest(query = ""): NextRequest {
  const { token } = mintSessionToken(42, SECRET);
  const url = `http://127.0.0.1/api/v1/market/movers${query ? `?${query}` : ""}`;
  return new NextRequest(url, {
    method: "GET",
    headers: { cookie: `${SESSION_COOKIE}=${token}` },
  });
}

function installDbPool(
  rows: Record<string, unknown>[] = [],
  mode: "ok" | "throw" = "ok",
): CapturedQuery[] {
  process.env.DATABASE_URL = "postgres://unit.test/koel";
  const captured: CapturedQuery[] = [];
  (globalThis as typeof globalThis & { __koelPgPool?: unknown }).__koelPgPool = {
    query: async (sql: string, params: unknown[] = []) => {
      captured.push({ sql, params });
      if (mode === "throw") {
        throw new Error("postgres://secret-user:secret-pass@db.internal/koel boom");
      }
      assert(
        sql.includes("INNER JOIN LATERAL"),
        "movers SQL must INNER JOIN LATERAL latest snapshots",
      );
      assert(!sql.toLowerCase().includes("cse.lk"), "SQL must not mention cse.lk");
      return { rows };
    },
  };
  return captured;
}

async function readBody(res: Response): Promise<MoversBody> {
  return (await res.json()) as MoversBody;
}

async function call(query: string, rows: Record<string, unknown>[] = []) {
  const captured = installDbPool(rows);
  process.env.DASH_SESSION_SECRET = SECRET;
  const res = await moversGet(makeRequest(query));
  const body = await readBody(res);
  return { res, body, captured };
}

async function testDefaultDirectionUpAndLimit(): Promise<void> {
  const { res, body, captured } = await call("");
  assert(res.status === 200, `default should 200, got ${res.status}`);
  assert(body.direction === "up", `default direction up, got ${body.direction}`);
  assert(body.limit === 20, `default limit 20, got ${body.limit}`);
  assert(captured.length === 1, "expected one SQL query");
  assert(
    captured[0].sql.includes("ps.change_pct > 0"),
    "default up must sign-filter change_pct > 0",
  );
  assert(
    captured[0].sql.includes("ps.change_pct DESC NULLS LAST"),
    "up sorts change_pct DESC",
  );
  assert(captured[0].params.includes(20), "params include default limit 20");
  assert(captured[0].params.includes(0), "params include offset 0");
}

async function testPostFilterDropsNullPctAfterFinite(): Promise<void> {
  const { res, body } = await call("direction=up&limit=5", [
    {
      symbol: "JKH.N0000",
      name: "John Keells",
      sector: null,
      price: "22.5",
      change: "0.3",
      change_pct: "1.35",
      ts: new Date("2026-07-11T09:00:00Z"),
    },
    {
      symbol: "BAD.N0000",
      name: null,
      sector: null,
      price: "1",
      change: null,
      change_pct: "Infinity",
      ts: null,
    },
    {
      symbol: "NAN.N0000",
      name: null,
      sector: null,
      price: "1",
      change: null,
      change_pct: "NaN",
      ts: null,
    },
    {
      symbol: "NEGINF.N0000",
      name: null,
      sector: null,
      price: "1",
      change: null,
      change_pct: "-Infinity",
      ts: null,
    },
    {
      symbol: "FLAT.N0000",
      name: null,
      sector: null,
      price: "1",
      change: "0",
      change_pct: "0",
      ts: null,
    },
    {
      // Wrong sign after finite coerce must not label as a gainer.
      symbol: "LOSER.N0000",
      name: null,
      sector: null,
      price: "10",
      change: "-0.5",
      change_pct: "-1.2",
      ts: null,
    },
  ]);
  assert(res.status === 200, `post-filter should 200, got ${res.status}`);
  assert(Array.isArray(body.items), "items array");
  assert(body.items!.length === 1, `only finite gainer kept, got ${body.items!.length}`);
  const only = body.items![0] as Record<string, unknown>;
  assert(only.symbol === "JKH.N0000", `expected JKH, got ${only.symbol}`);
  assert(only.change_pct === 1.35, `JKH pct finite, got ${only.change_pct}`);
}

async function testPostFilterDownDropsNonFiniteWrongSignAndFlat(): Promise<void> {
  const { res, body } = await call("direction=down&limit=5", [
    {
      symbol: "COMB.N0000",
      name: "Commercial Bank",
      sector: null,
      price: "95.5",
      change: "-1.4",
      change_pct: "-1.44",
      ts: new Date("2026-07-11T09:00:00Z"),
    },
    {
      symbol: "BAD.N0000",
      name: null,
      sector: null,
      price: "1",
      change: null,
      change_pct: "-Infinity",
      ts: null,
    },
    {
      symbol: "NAN.N0000",
      name: null,
      sector: null,
      price: "1",
      change: null,
      change_pct: "NaN",
      ts: null,
    },
    {
      symbol: "FLAT.N0000",
      name: null,
      sector: null,
      price: "1",
      change: "0",
      change_pct: "0",
      ts: null,
    },
    {
      // Opposite sign must not appear under direction=down.
      symbol: "GAIN.N0000",
      name: null,
      sector: null,
      price: "10",
      change: "0.5",
      change_pct: "1.2",
      ts: null,
    },
  ]);
  assert(res.status === 200, `down post-filter should 200, got ${res.status}`);
  assert(Array.isArray(body.items), "items array");
  assert(
    body.items!.length === 1,
    `only finite loser kept, got ${body.items!.length}`,
  );
  const only = body.items![0] as Record<string, unknown>;
  assert(only.symbol === "COMB.N0000", `expected COMB, got ${only.symbol}`);
  assert(only.change_pct === -1.44, `COMB pct finite, got ${only.change_pct}`);
  assert(only.price === 95.5, `COMB price finite, got ${only.price}`);
}

async function testFinitePriceNullDoesNotDropFinitePctMover(): Promise<void> {
  // Drop fence is change_pct only — non-finite price nulls out but row stays.
  const { res, body } = await call("direction=up&limit=3", [
    {
      symbol: "JKH.N0000",
      name: "John Keells",
      sector: null,
      price: "NaN",
      change: "Infinity",
      change_pct: "2.5",
      ts: new Date("2026-07-11T09:00:00Z"),
    },
  ]);
  assert(res.status === 200, `finite pct mover should 200, got ${res.status}`);
  assert(Array.isArray(body.items) && body.items.length === 1, "row kept");
  const row = body.items![0] as Record<string, unknown>;
  assert(row.symbol === "JKH.N0000", "finite pct gainer kept");
  assert(row.price === null, `non-finite price → null, got ${row.price}`);
  assert(row.change === null, `non-finite change → null, got ${row.change}`);
  assert(row.change_pct === 2.5, `finite pct kept, got ${row.change_pct}`);
}

async function testDirectionDownSignFilter(): Promise<void> {
  const { res, body, captured } = await call("direction=down&limit=5");
  assert(res.status === 200, `direction=down should 200, got ${res.status}`);
  assert(body.direction === "down", `direction echo down, got ${body.direction}`);
  assert(body.limit === 5, `limit echo 5, got ${body.limit}`);
  assert(
    captured[0].sql.includes("ps.change_pct < 0"),
    "down must sign-filter change_pct < 0",
  );
  assert(
    !captured[0].sql.includes("ps.change_pct > 0"),
    "down must not use > 0 filter",
  );
  assert(
    captured[0].sql.includes("ps.change_pct ASC NULLS LAST"),
    "down sorts change_pct ASC",
  );
}

async function testInvalidDirectionRejected(): Promise<void> {
  for (const raw of ["sideways", "UPP", "drop table", "both"]) {
    const { res, body, captured } = await call(
      `direction=${encodeURIComponent(raw)}`,
    );
    assert(res.status === 400, `invalid direction ${raw} → 400, got ${res.status}`);
    const code =
      typeof body.error === "object" && body.error !== null
        ? body.error.code
        : undefined;
    assert(code === "validation_error", `expected validation_error, got ${code}`);
    assert(captured.length === 0, `invalid direction must not hit DB (${raw})`);
  }
}

async function testLimitClampAndInvalidFallback(): Promise<void> {
  {
    const { res, body, captured } = await call("limit=9999");
    assert(res.status === 200, `limit clamp should 200, got ${res.status}`);
    assert(body.limit === 50, `limit clamped to 50, got ${body.limit}`);
    assert(captured[0].params.includes(50), "SQL params use clamped 50");
  }
  for (const raw of ["0", "-3", "nope"]) {
    const { res, body, captured } = await call(`limit=${raw}`);
    assert(res.status === 200, `invalid limit ${raw} should 200, got ${res.status}`);
    assert(body.limit === 20, `invalid limit ${raw} → default 20, got ${body.limit}`);
    assert(captured[0].params.includes(20), `params use default for limit=${raw}`);
  }
}

async function testSessionRequiredAndNoCsrf(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  const bare = await moversGet(
    new NextRequest("http://127.0.0.1/api/v1/market/movers", { method: "GET" }),
  );
  assert(bare.status === 401, `no session → 401, got ${bare.status}`);

  const withSession = await moversGet(makeRequest("limit=1"));
  assert(withSession.status === 200, `GET without CSRF must 200, got ${withSession.status}`);
}

async function testDbErrorDoesNotDiscloseInternals(): Promise<void> {
  installDbPool([], "throw");
  process.env.DASH_SESSION_SECRET = SECRET;
  const res = await moversGet(makeRequest(""));
  const body = await readBody(res);
  assert(res.status === 503, `db failure → 503, got ${res.status}`);
  const code =
    typeof body.error === "object" && body.error !== null
      ? body.error.code
      : undefined;
  const message =
    typeof body.error === "object" && body.error !== null
      ? body.error.message
      : undefined;
  assert(code === "degraded", `expected degraded, got ${code}`);
  assert(
    message === "Database unavailable.",
    `stable message, got ${message}`,
  );
  const dumped = JSON.stringify(body);
  assert(!dumped.includes("secret-pass"), "must not leak DSN password");
  assert(!dumped.includes("db.internal"), "must not leak DB host");
  assert(!dumped.includes("postgres://"), "must not leak connection string");
}

async function testFiniteEgressAndNoQFilter(): Promise<void> {
  assert(toFiniteNumber(null) === null, "null → null");
  assert(toFiniteNumber(undefined) === null, "undefined → null");
  assert(toFiniteNumber(NaN) === null, "NaN → null");
  assert(toFiniteNumber(Infinity) === null, "Infinity → null");
  assert(toFiniteNumber(-Infinity) === null, "-Infinity → null");
  assert(toFiniteNumber("Infinity") === null, "Infinity string → null");
  assert(toFiniteNumber("-Infinity") === null, "-Infinity string → null");
  assert(toFiniteNumber("NaN") === null, "NaN string → null");
  assert(toFiniteNumber("1.25") === 1.25, "numeric string → number");
  assert(toFiniteNumber(0) === 0, "zero kept");
  assert(toFiniteNumber(-3.5) === -3.5, "negative finite kept");
  assert(toFiniteNumber("nope") === null, "non-numeric → null");
  assert(toFiniteNumber("") === null, "empty string → null (not Number('')→0)");
  assert(toFiniteNumber("1e2") === null, "sci-notation → null");
  assert(toFiniteNumber(true) === null, "boolean → null");
  assert(toFiniteNumber([]) === null, "array → null");

  const { res, body, captured } = await call(
    "direction=up&limit=3",
    [
      {
        symbol: "JKH.N0000",
        name: "John Keells",
        sector: null,
        price: "22.5",
        change: "0.3",
        change_pct: "1.35",
        ts: new Date("2026-07-11T09:00:00Z"),
      },
      {
        symbol: "BAD.N0000",
        name: null,
        sector: null,
        price: "NaN",
        change: null,
        change_pct: "Infinity",
        ts: null,
      },
    ],
  );
  assert(res.status === 200, `finite egress should 200, got ${res.status}`);
  assert(Array.isArray(body.items) && body.items.length === 1, "only finite gainer");
  const jkh = body.items![0] as Record<string, unknown>;
  assert(jkh.price === 22.5, `JKH price finite, got ${jkh.price}`);
  assert(jkh.change_pct === 1.35, `JKH change_pct finite, got ${jkh.change_pct}`);
  assert(jkh.symbol === "JKH.N0000", "non-finite pct row dropped from movers");
  // Thin fence: movers must not accept q / LIKE search.
  assert(!captured[0].sql.includes("LIKE"), "movers must not add LIKE q filter");
  assert(!captured[0].sql.toLowerCase().includes("sector ="), "no sector filter");
}

async function testCaseInsensitiveDirection(): Promise<void> {
  const { res, body, captured } = await call("direction=DOWN");
  assert(res.status === 200, `DOWN should 200, got ${res.status}`);
  assert(body.direction === "down", `DOWN normalizes to down, got ${body.direction}`);
  assert(captured[0].sql.includes("ps.change_pct < 0"), "DOWN → down filter");
}

async function main(): Promise<void> {
  process.env.DASH_SESSION_REVOKE_CHECK = "0";
  await testDefaultDirectionUpAndLimit();
  await testPostFilterDropsNullPctAfterFinite();
  await testPostFilterDownDropsNonFiniteWrongSignAndFlat();
  await testFinitePriceNullDoesNotDropFinitePctMover();
  await testDirectionDownSignFilter();
  await testInvalidDirectionRejected();
  await testLimitClampAndInvalidFallback();
  await testSessionRequiredAndNoCsrf();
  await testDbErrorDoesNotDiscloseInternals();
  await testFiniteEgressAndNoQFilter();
  await testCaseInsensitiveDirection();
  console.log("WEB_MOVERS_ROUTE_UNIT_OK");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
