/**
 * GET /api/v1/symbols — query validation + browse SQL harness.
 *
 * Invoked from web/ (cwd + module root) so `next` resolves:
 *   pytest tests/test_web_route_regressions.py::test_symbols_list_query_validation_unit
 */
import { NextRequest } from "next/server";

import { GET as symbolsGet } from "./src/app/api/v1/symbols/route.ts";
import { toFiniteNumber } from "./src/lib/api/market-browse.ts";
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
  total?: number;
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
  totalCount?: number,
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
        "browse SQL must INNER JOIN LATERAL latest snapshots",
      );
      assert(
        !sql.includes("LEFT JOIN LATERAL"),
        "browse SQL must not LEFT JOIN stubs without snapshots",
      );
      assert(sql.includes("price_snapshots"), "browse SQL must read price_snapshots");
      assert(!sql.toLowerCase().includes("cse.lk"), "SQL must not mention cse.lk");
      if (/COUNT\s*\(/i.test(sql)) {
        return { rows: [{ n: totalCount ?? rows.length }] };
      }
      return { rows };
    },
  };
  return captured;
}

function browseQuery(captured: CapturedQuery[]): CapturedQuery {
  const hit = captured.find((c) => /LIMIT\s+\$/i.test(c.sql));
  assert(hit, "expected browse LIMIT query");
  return hit;
}

function countQuery(captured: CapturedQuery[]): CapturedQuery {
  const hit = captured.find((c) => /COUNT\s*\(/i.test(c.sql));
  assert(hit, "expected COUNT query");
  return hit;
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
  assert(typeof body.total === "number", "response includes total");
  assert(captured.length === 2, "expected browse + count SQL queries");
  const browse = browseQuery(captured);
  countQuery(captured);
  assert(browse.params.includes(50), "params include default limit 50");
  assert(browse.params.includes(0), "params include offset 0");
  assert(
    browse.sql.includes("ps.change_pct DESC NULLS LAST"),
    "default ORDER BY change_pct DESC",
  );
}

async function testLimitClampToMax200(): Promise<void> {
  const { res, body, captured } = await call("limit=9999");
  assert(res.status === 200, `limit clamp should 200, got ${res.status}`);
  assert(body.limit === 200, `limit clamped to 200, got ${body.limit}`);
  const browse = browseQuery(captured);
  assert(browse.params.includes(200), "SQL params use clamped 200");
  assert(!browse.params.includes(9999), "raw oversize limit must not reach SQL");
}

async function testInvalidLimitFallsBackToDefault(): Promise<void> {
  for (const raw of ["0", "-5", "nope", ""]) {
    const query = raw === "" ? "limit=" : `limit=${raw}`;
    const { res, body, captured } = await call(query);
    assert(res.status === 200, `invalid limit ${raw} should 200, got ${res.status}`);
    assert(body.limit === 50, `invalid limit ${raw} → default 50, got ${body.limit}`);
    assert(
      browseQuery(captured).params.includes(50),
      `params use default for limit=${raw}`,
    );
  }
}

async function testSortWhitelist(): Promise<void> {
  {
    const { res, body, captured } = await call("sort=symbol");
    assert(res.status === 200, `sort=symbol should 200, got ${res.status}`);
    assert(body.sort === "symbol", `sort echo symbol, got ${body.sort}`);
    const browse = browseQuery(captured);
    assert(browse.sql.includes("s.symbol ASC"), "ORDER BY symbol ASC");
    assert(
      !browse.sql.includes("ps.change_pct DESC"),
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
      browseQuery(captured).sql.includes("ps.change_pct DESC NULLS LAST"),
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
    assert(
      browseQuery(captured).sql.includes("s.symbol ASC"),
      "SYMBOL → symbol ORDER BY",
    );
  }
}

async function testEmptyBoardReturnsEmptyItems(): Promise<void> {
  const { res, body, captured } = await call("limit=10", []);
  assert(res.status === 200, `empty board should 200, got ${res.status}`);
  assert(Array.isArray(body.items) && body.items.length === 0, "empty items[]");
  assert(body.limit === 10, `limit echoed 10, got ${body.limit}`);
  assert(body.total === 0, `empty board total 0, got ${body.total}`);
  assert(
    browseQuery(captured).sql.includes("INNER JOIN LATERAL"),
    "empty board still INNER JOIN",
  );
}

async function testSessionOptional(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  // Public market browse — session optional.
  const res = await symbolsGet(
    new NextRequest("http://127.0.0.1/api/v1/symbols", { method: "GET" }),
  );
  assert(res.status === 200, `no session → 200, got ${res.status}`);
  const body = await readBody(res);
  assert(body.error === undefined, `expected no error body, got ${JSON.stringify(body)}`);
}



async function testGetDoesNotRequireCsrf(): Promise<void> {
  installDbPool();
  process.env.DASH_SESSION_SECRET = SECRET;
  // Session cookie only — no X-CSRF-Token / koel_csrf. Safe GET must succeed.
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
  const browse = browseQuery(captured);
  assert(browse.sql.includes("ESCAPE '\\'"), "LIKE must use ESCAPE '\\'");
  assert(!browse.sql.includes(raw), "raw q must not be interpolated into SQL text");
  const expected = `%${escapeLikePattern(raw.toUpperCase())}%`;
  assert(
    browse.params[0] === expected,
    `LIKE param must be escaped, got ${JSON.stringify(browse.params[0])}`,
  );
  assert(
    countQuery(captured).params[0] === expected,
    "COUNT query must use the same escaped LIKE param",
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
    browseQuery(captured).params.includes(MAX_SYMBOLS_OFFSET),
    "SQL params use clamped offset",
  );
}

async function testFiniteNumberEgress(): Promise<void> {
  // Shared browse coerce (w13): NaN/±Infinity → null; symbols keep the row.
  assert(toFiniteNumber(null) === null, "null → null");
  assert(toFiniteNumber(NaN) === null, "NaN → null");
  assert(toFiniteNumber(Infinity) === null, "Infinity → null");
  assert(toFiniteNumber(-Infinity) === null, "-Infinity → null");
  assert(toFiniteNumber("Infinity") === null, "Infinity string → null");
  assert(toFiniteNumber("-Infinity") === null, "-Infinity string → null");
  assert(toFiniteNumber("NaN") === null, "NaN string → null");
  assert(toFiniteNumber("22.5") === 22.5, "numeric string → number");
  assert(toFiniteNumber(-1.44) === -1.44, "negative finite kept");
  assert(toFiniteNumber("nope") === null, "non-numeric → null");
  assert(toFiniteNumber("") === null, "empty string → null (not Number('')→0)");
  assert(toFiniteNumber("1e2") === null, "sci-notation → null");
  assert(toFiniteNumber(true) === null, "boolean → null");
  assert(toFiniteNumber([]) === null, "array → null");

  const { res, body } = await call("limit=10", [
    {
      symbol: "JKH.N0000",
      name: "John Keells",
      sector: "Diversified",
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
      change: "Infinity",
      change_pct: "-Infinity",
      ts: null,
    },
    {
      symbol: "FLAT.N0000",
      name: null,
      sector: null,
      price: "100",
      change: "0",
      change_pct: "0",
      ts: null,
    },
  ]);
  assert(res.status === 200, `finite egress should 200, got ${res.status}`);
  assert(Array.isArray(body.items), "items array");
  // Unlike movers, symbols do not drop non-finite pct rows — only null fields.
  assert(body.items!.length === 3, `all rows kept, got ${body.items!.length}`);

  const bySymbol = Object.fromEntries(
    (body.items as Record<string, unknown>[]).map((r) => [r.symbol, r]),
  );
  const jkh = bySymbol["JKH.N0000"];
  assert(jkh, "JKH present");
  assert(jkh.price === 22.5, `JKH price finite, got ${jkh.price}`);
  assert(jkh.change === 0.3, `JKH change finite, got ${jkh.change}`);
  assert(jkh.change_pct === 1.35, `JKH pct finite, got ${jkh.change_pct}`);

  const bad = bySymbol["BAD.N0000"];
  assert(bad, "BAD row kept (symbols browse, not movers drop)");
  assert(bad.price === null, `non-finite price → null, got ${bad.price}`);
  assert(bad.change === null, `non-finite change → null, got ${bad.change}`);
  assert(
    bad.change_pct === null,
    `non-finite change_pct → null, got ${bad.change_pct}`,
  );

  const flat = bySymbol["FLAT.N0000"];
  assert(flat, "FLAT present");
  assert(flat.change_pct === 0, `zero pct kept, got ${flat.change_pct}`);
  assert(flat.price === 100, `FLAT price finite, got ${flat.price}`);
}

async function main(): Promise<void> {
  process.env.DASH_SESSION_REVOKE_CHECK = "0";
  await testDefaultLimitAndSort();
  await testLimitClampToMax200();
  await testInvalidLimitFallsBackToDefault();
  await testSortWhitelist();
  await testEmptyBoardReturnsEmptyItems();
  await testSessionOptional();
  await testGetDoesNotRequireCsrf();
  await testLikeMetacharEscape();
  await testQueryLengthCapAndOffsetClamp();
  await testFiniteNumberEgress();
  await testDbErrorDoesNotDiscloseInternals();
  console.log("WEB_SYMBOLS_ROUTE_UNIT_OK");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
