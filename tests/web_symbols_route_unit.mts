/**
 * GET /api/v1/symbols — query validation + browse SQL harness.
 *
 * Invoked from web/ (cwd + module root) so `next` resolves:
 *   pytest tests/test_web_route_regressions.py::test_symbols_list_query_validation_unit
 */
import { NextRequest } from "next/server";

import { GET as symbolsGet } from "./src/app/api/v1/symbols/route.ts";
import {
  MAX_MARKET_Q_LENGTH,
  MAX_SYMBOLS_OFFSET,
  escapeLikePattern,
  normalizeMarketQuery,
} from "./src/lib/api/market-query.ts";
import { SESSION_COOKIE } from "./src/lib/auth/config.ts";
import { mintSessionToken } from "./src/lib/auth/session.ts";

const SECRET = "web-symbols-route-unit-secret-not-for-prod";

type SymbolsBody = {
  items?: unknown[];
  limit?: number;
  offset?: number;
  sort?: string;
  q?: string | null;
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
  const url = `http://127.0.0.1/api/v1/symbols${query ? `?${query}` : ""}`;
  return new NextRequest(url, {
    method: "GET",
    headers: { cookie: `${SESSION_COOKIE}=${token}` },
  });
}

function installDbPool(
  rows: Record<string, unknown>[] = [],
  mode: "ok" | "throw" = "ok",
): CapturedQuery[] {
  process.env.DATABASE_URL = "postgres://unit.test/chime";
  const captured: CapturedQuery[] = [];
  (globalThis as typeof globalThis & { __chimePgPool?: unknown }).__chimePgPool = {
    query: async (sql: string, params: unknown[] = []) => {
      captured.push({ sql, params });
      if (mode === "throw") {
        throw new Error("postgres://secret-user:secret-pass@db.internal/chime boom");
      }
      assert(
        sql.includes("INNER JOIN LATERAL"),
        "browse SQL must INNER JOIN LATERAL latest snapshots",
      );
      assert(
        !sql.includes("LEFT JOIN LATERAL"),
        "browse SQL must not LEFT JOIN stubs without snapshots",
      );
      assert(sql.includes("price_snapshots"), "browse SQL must read price_snapshots");
      assert(!sql.toLowerCase().includes("cse.lk"), "SQL must not mention cse.lk");
      return { rows };
    },
  };
  return captured;
}

async function readBody(res: Response): Promise<SymbolsBody> {
  return (await res.json()) as SymbolsBody;
}

async function call(query: string, rows: Record<string, unknown>[] = []) {
  const captured = installDbPool(rows);
  process.env.DASH_SESSION_SECRET = SECRET;
  const res = await symbolsGet(makeRequest(query));
  const body = await readBody(res);
  return { res, body, captured };
}

async function testDefaultLimitAndSort(): Promise<void> {
  const { res, body, captured } = await call("");
  assert(res.status === 200, `default query should 200, got ${res.status}`);
  assert(body.limit === 50, `default limit 50, got ${body.limit}`);
  assert(body.offset === 0, `default offset 0, got ${body.offset}`);
  assert(body.sort === "change_pct", `default sort change_pct, got ${body.sort}`);
  assert(body.q === null, `default q null, got ${body.q}`);
  assert(captured.length === 1, "expected one SQL query");
  assert(captured[0].params.includes(50), "params include default limit 50");
  assert(captured[0].params.includes(0), "params include offset 0");
  assert(
    captured[0].sql.includes("ps.change_pct DESC NULLS LAST"),
    "default ORDER BY change_pct DESC",
  );
}

async function testLimitClampToMax200(): Promise<void> {
  const { res, body, captured } = await call("limit=9999");
  assert(res.status === 200, `limit clamp should 200, got ${res.status}`);
  assert(body.limit === 200, `limit clamped to 200, got ${body.limit}`);
  assert(captured[0].params.includes(200), "SQL params use clamped 200");
  assert(!captured[0].params.includes(9999), "raw oversize limit must not reach SQL");
}

async function testInvalidLimitFallsBackToDefault(): Promise<void> {
  for (const raw of ["0", "-5", "nope", ""]) {
    const query = raw === "" ? "limit=" : `limit=${raw}`;
    const { res, body, captured } = await call(query);
    assert(res.status === 200, `invalid limit ${raw} should 200, got ${res.status}`);
    assert(body.limit === 50, `invalid limit ${raw} → default 50, got ${body.limit}`);
    assert(captured[0].params.includes(50), `params use default for limit=${raw}`);
  }
}

async function testSortWhitelist(): Promise<void> {
  {
    const { res, body, captured } = await call("sort=symbol");
    assert(res.status === 200, `sort=symbol should 200, got ${res.status}`);
    assert(body.sort === "symbol", `sort echo symbol, got ${body.sort}`);
    assert(captured[0].sql.includes("s.symbol ASC"), "ORDER BY symbol ASC");
    assert(
      !captured[0].sql.includes("ps.change_pct DESC"),
      "symbol sort must not use change_pct order",
    );
  }
  {
    const { res, body, captured } = await call("sort=volume");
    assert(res.status === 200, `unknown sort should 200, got ${res.status}`);
    assert(
      body.sort === "change_pct",
      `unknown sort falls back to change_pct, got ${body.sort}`,
    );
    assert(
      captured[0].sql.includes("ps.change_pct DESC NULLS LAST"),
      "unknown sort uses change_pct ORDER BY",
    );
  }
  {
    const { res, body } = await call("sort=DROP%20TABLE");
    assert(res.status === 200, "injection-ish sort should still 200");
    assert(body.sort === "change_pct", "non-whitelist sort never echoed");
  }
  {
    const { res, body, captured } = await call("sort=SYMBOL");
    assert(res.status === 200, `case-insensitive symbol sort should 200`);
    assert(body.sort === "symbol", `SYMBOL normalizes to symbol, got ${body.sort}`);
    assert(captured[0].sql.includes("s.symbol ASC"), "SYMBOL → symbol ORDER BY");
  }
}

async function testEmptyBoardReturnsEmptyItems(): Promise<void> {
  const { res, body, captured } = await call("limit=10", []);
  assert(res.status === 200, `empty board should 200, got ${res.status}`);
  assert(Array.isArray(body.items) && body.items.length === 0, "empty items[]");
  assert(body.limit === 10, `limit echoed 10, got ${body.limit}`);
  assert(captured[0].sql.includes("INNER JOIN LATERAL"), "empty board still INNER JOIN");
}

async function testSessionRequired(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  const res = await symbolsGet(
    new NextRequest("http://127.0.0.1/api/v1/symbols", { method: "GET" }),
  );
  const body = await readBody(res);
  assert(res.status === 401, `no session → 401, got ${res.status}`);
  const code =
    typeof body.error === "object" && body.error !== null
      ? body.error.code
      : body.error;
  assert(code === "unauthorized", `expected unauthorized, got ${code}`);
}



async function testGetDoesNotRequireCsrf(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  // Session cookie only — no X-CSRF-Token / chime_csrf. Safe GET must succeed.
  const res = await symbolsGet(makeRequest("limit=1"));
  assert(res.status === 200, `GET without CSRF must 200, got ${res.status}`);
  const body = await readBody(res);
  assert(body.error === undefined, "GET without CSRF must not csrf_failed");
}

async function testDbErrorDoesNotDiscloseInternals(): Promise<void> {
  installDbPool([], "throw");
  process.env.DASH_SESSION_SECRET = SECRET;
  const res = await symbolsGet(makeRequest(""));
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

async function testLikeMetacharEscape(): Promise<void> {
  const raw = "a%b_c\\d";
  const { res, body, captured } = await call(`q=${encodeURIComponent(raw)}`);
  assert(res.status === 200, `q LIKE escape should 200, got ${res.status}`);
  assert(body.q === raw, `sanitized q echoed, got ${JSON.stringify(body.q)}`);
  const sql = captured[0].sql;
  assert(sql.includes("ESCAPE '\\'"), "LIKE must use ESCAPE '\\'");
  assert(!sql.includes(raw), "raw q must not be interpolated into SQL text");
  const expected = `%${escapeLikePattern(raw.toUpperCase())}%`;
  assert(
    captured[0].params[0] === expected,
    `LIKE param must be escaped, got ${JSON.stringify(captured[0].params[0])}`,
  );
}

async function testQueryLengthCapAndOffsetClamp(): Promise<void> {
  assert(escapeLikePattern("%_") === "\\%\\_", "escape % and _");
  assert(
    normalizeMarketQuery("X".repeat(MAX_MARKET_Q_LENGTH + 40)).length ===
      MAX_MARKET_Q_LENGTH,
    "normalizeMarketQuery caps length",
  );
  assert(
    normalizeMarketQuery("ab" + String.fromCharCode(0) + "c" + String.fromCharCode(10) + "d") ===
      "abcd",
    "NUL/LF controls stripped",
  );
  const over = "X".repeat(MAX_MARKET_Q_LENGTH + 40);
  const { res, body, captured } = await call(
    `q=${encodeURIComponent(over)}&offset=999999`,
  );
  assert(res.status === 200, "overlong q still 200");
  assert(
    typeof body.q === "string" && body.q.length === MAX_MARKET_Q_LENGTH,
    `response q capped to ${MAX_MARKET_Q_LENGTH}`,
  );
  assert(body.offset === MAX_SYMBOLS_OFFSET, `offset clamped, got ${body.offset}`);
  assert(
    captured[0].params.includes(MAX_SYMBOLS_OFFSET),
    "SQL params use clamped offset",
  );
}

async function main(): Promise<void> {
  await testDefaultLimitAndSort();
  await testLimitClampToMax200();
  await testInvalidLimitFallsBackToDefault();
  await testSortWhitelist();
  await testEmptyBoardReturnsEmptyItems();
  await testSessionRequired();
  await testGetDoesNotRequireCsrf();
  await testLikeMetacharEscape();
  await testQueryLengthCapAndOffsetClamp();
  await testDbErrorDoesNotDiscloseInternals();
  console.log("WEB_SYMBOLS_ROUTE_UNIT_OK");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
