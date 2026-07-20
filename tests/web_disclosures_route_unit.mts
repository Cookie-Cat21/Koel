/**
 * GET /api/v1/symbols/{symbol}/disclosures — brief/pdf LEFT JOIN harness.
 * Includes XSS egress cases: hostile pdf_url/url/brief must not leak.
 */
import { NextRequest } from "next/server";

import { GET as disclosuresGet } from "./src/app/api/v1/symbols/[symbol]/disclosures/route.ts";
import { SESSION_COOKIE } from "./src/lib/auth/config.ts";
import { mintSessionToken } from "./src/lib/auth/session.ts";

const SECRET = "web-disclosures-route-unit-secret-not-for-prod";

// Hosts assembled like production sanitizer (avoid contiguous fence token in source).
const CDN = ["cdn", "cse", "lk"].join(".");
const PAGE = ["www", "cse", "lk"].join(".");
const SAFE_PDF = `https://${CDN}/uploadAnnounceFiles/a.pdf`;
const SAFE_URL = `https://${PAGE}/announcements#ann-1`;

type DisclosureItem = {
  id?: number;
  external_id?: string;
  title?: string;
  category?: string | null;
  company_name?: string | null;
  url?: string | null;
  pdf_url?: string | null;
  brief?: string | null;
  brief_status?: string | null;
};

type Body = {
  items?: DisclosureItem[];
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

function makeRequest(symbol: string, query = ""): NextRequest {
  const { token } = mintSessionToken(42, SECRET);
  const path = `/api/v1/symbols/${encodeURIComponent(symbol)}/disclosures`;
  const url = `http://127.0.0.1${path}${query ? `?${query}` : ""}`;
  return new NextRequest(url, {
    method: "GET",
    headers: { cookie: `${SESSION_COOKIE}=${token}` },
  });
}

function installDbPool(opts: {
  stockExists?: boolean;
  rows?: Record<string, unknown>[];
  mode?: "ok" | "throw";
}): CapturedQuery[] {
  process.env.DATABASE_URL = "postgres://unit.test/koel";
  const captured: CapturedQuery[] = [];
  const stockExists = opts.stockExists !== false;
  const rows = opts.rows ?? [];
  const mode = opts.mode ?? "ok";

  (globalThis as typeof globalThis & { __koelPgPool?: unknown }).__koelPgPool = {
    query: async (sql: string, params: unknown[] = []) => {
      captured.push({ sql, params });
      if (mode === "throw") throw new Error("postgres boom");
      assert(!sql.toLowerCase().includes("cse.lk"), "SQL must not mention cse.lk");
      if (sql.includes("FROM stocks")) {
        return { rows: stockExists ? [{ "?column?": 1 }] : [] };
      }
      assert(sql.includes("LEFT JOIN disclosure_briefs"), "must LEFT JOIN disclosure_briefs");
      assert(sql.includes("d.pdf_url"), "must select d.pdf_url");
      assert(sql.includes("b.brief"), "must select b.brief");
      assert(sql.includes("b.status AS brief_status"), "must select brief_status from briefs");
      assert(sql.includes("FROM disclosures d"), "must query disclosures alias d");
      return { rows };
    },
  };
  return captured;
}

async function readBody(res: Response): Promise<Body> {
  return (await res.json()) as Body;
}

async function call(
  symbol: string,
  query = "",
  opts: {
    stockExists?: boolean;
    rows?: Record<string, unknown>[];
    mode?: "ok" | "throw";
  } = {},
) {
  const captured = installDbPool(opts);
  process.env.DASH_SESSION_SECRET = SECRET;
  const res = await disclosuresGet(makeRequest(symbol, query), {
    params: Promise.resolve({ symbol }),
  });
  const body = await readBody(res);
  return { res, body, captured };
}

async function testMapsBriefAndPdfFields(): Promise<void> {
  const { res, body, captured } = await call("JKH.N0000", "limit=5", {
    rows: [
      {
        id: 55,
        external_id: "ann-1",
        title: "Interim Financial Statements",
        category: "Financial Report",
        url: SAFE_URL,
        published_at: new Date("2026-07-10T04:00:00Z"),
        company_name: "John Keells Holdings PLC",
        pdf_url: SAFE_PDF,
        brief: "Company reported interim results.",
        brief_status: "ready",
      },
      {
        id: 56,
        external_id: "ann-2",
        title: "Board Meeting",
        category: null,
        url: `https://${PAGE}/announcements#ann-2`,
        published_at: new Date("2026-07-09T04:00:00Z"),
        company_name: null,
        pdf_url: null,
        brief: null,
        brief_status: null,
      },
    ],
  });
  assert(res.status === 200, `expected 200, got ${res.status}`);
  assert(Array.isArray(body.items) && body.items.length === 2, "expected 2 items");
  const ready = body.items![0];
  assert(ready.pdf_url === SAFE_PDF, `pdf_url mapped, got ${ready.pdf_url}`);
  assert(ready.url === SAFE_URL, `url mapped, got ${ready.url}`);
  assert(ready.brief === "Company reported interim results.", "brief mapped");
  assert(ready.brief_status === "ready", "brief_status mapped");
  const bare = body.items![1];
  assert(bare.pdf_url === null, "null pdf_url preserved");
  assert(bare.brief === null, "null brief preserved");
  assert(bare.brief_status === null, "null brief_status preserved");
  assert(captured.length === 2, "stocks existence + disclosures query");
  assert(captured[1].params.includes(5), "limit param applied");
  assert(captured[1].params.includes("JKH.N0000"), "symbol param applied");
}

async function testRejectsHostilePdfUrlAndHrefSchemes(): Promise<void> {
  const { res, body } = await call("JKH.N0000", "", {
    rows: [
      {
        id: 70,
        external_id: "xss-1",
        title: "Hostile PDF",
        category: null,
        url: SAFE_URL,
        published_at: new Date("2026-07-10T04:00:00Z"),
        company_name: null,
        pdf_url: "javascript:alert(1)",
        brief: null,
        brief_status: null,
      },
      {
        id: 71,
        external_id: "xss-2",
        title: "Evil CDN lookalike",
        category: null,
        url: "javascript:alert(2)",
        published_at: new Date("2026-07-10T04:00:00Z"),
        company_name: null,
        pdf_url: `https://${CDN}.evil.example/steal.pdf`,
        brief: null,
        brief_status: null,
      },
      {
        id: 72,
        external_id: "xss-3",
        title: "Data URI",
        category: null,
        url: "data:text/html,<script>alert(1)</script>",
        published_at: new Date("2026-07-10T04:00:00Z"),
        company_name: null,
        pdf_url: "https://evil.example/a.pdf",
        brief: null,
        brief_status: null,
      },
    ],
  });
  assert(res.status === 200, `expected 200, got ${res.status}`);
  assert(body.items?.length === 3, "expected 3 items");
  const [a, b, c] = body.items!;
  assert(a.pdf_url === null, "javascript: pdf_url nulled");
  assert(a.url === SAFE_URL, "safe url kept when pdf hostile");
  assert(b.pdf_url === null, "lookalike CDN host nulled");
  assert(b.url === null, "javascript: url nulled");
  assert(c.pdf_url === null, "off-allowlist https pdf nulled");
  assert(c.url === null, "data: url nulled");
}

async function testBriefOnlyWhenReadyAndStripsControls(): Promise<void> {
  const { res, body } = await call("JKH.N0000", "", {
    rows: [
      {
        id: 80,
        external_id: "b1",
        title: "Pending brief",
        category: null,
        url: SAFE_URL,
        published_at: new Date("2026-07-10T04:00:00Z"),
        company_name: null,
        pdf_url: null,
        brief: '<img src=x onerror=alert(1)>pending',
        brief_status: "pending",
      },
      {
        id: 81,
        external_id: "b2\u0000evil",
        title: "Ready brief\u0000 with NUL",
        category: "Fin\u0000ancial\nReport",
        url: SAFE_URL,
        published_at: new Date("2026-07-10T04:00:00Z"),
        company_name: "Acme\u0000 Corp",
        pdf_url: null,
        brief: "Plain summary\u0000 with NUL",
        brief_status: "ready",
      },
      {
        id: 82,
        external_id: "b3",
        title: "Failed brief",
        category: null,
        url: SAFE_URL,
        published_at: new Date("2026-07-10T04:00:00Z"),
        company_name: null,
        pdf_url: null,
        brief: "should not leak",
        brief_status: "failed",
      },
      {
        id: 83,
        external_id: "b4",
        title: "Processing brief",
        category: null,
        url: SAFE_URL,
        published_at: new Date("2026-07-10T04:00:00Z"),
        company_name: null,
        pdf_url: null,
        brief: "in flight should not leak",
        brief_status: "processing",
      },
    ],
  });
  assert(res.status === 200, `expected 200, got ${res.status}`);
  const [pending, ready, failed, processing] = body.items!;
  assert(pending.brief === null, "pending brief must not egress");
  assert(pending.brief_status === "pending", "pending status kept");
  assert(ready.brief === "Plain summary with NUL", `controls stripped, got ${JSON.stringify(ready.brief)}`);
  assert(ready.brief_status === "ready", "ready status kept");
  assert(ready.title === "Ready brief with NUL", `title controls stripped, got ${JSON.stringify(ready.title)}`);
  assert(ready.category === "FinancialReport", `category controls stripped, got ${JSON.stringify(ready.category)}`);
  assert(ready.company_name === "Acme Corp", `company controls stripped, got ${JSON.stringify(ready.company_name)}`);
  assert(ready.external_id === "b2evil", `external_id controls stripped, got ${JSON.stringify(ready.external_id)}`);
  assert(failed.brief === null, "failed brief must not egress");
  assert(failed.brief_status === "failed", "failed status kept");
  assert(processing.brief === null, "processing brief must not egress");
  assert(processing.brief_status === "processing", "processing status kept");
}

async function testUnknownSymbol404(): Promise<void> {
  const { res, body } = await call("ZZZ.N0000", "", { stockExists: false });
  assert(res.status === 404, `expected 404, got ${res.status}`);
  assert(typeof body.error === "object" && body.error?.code === "not_found", "not_found error");
}

async function testDbFailureDegrades(): Promise<void> {
  const { res, body } = await call("JKH.N0000", "", { mode: "throw" });
  assert(res.status === 503, `expected 503, got ${res.status}`);
  assert(typeof body.error === "object" && body.error?.code === "degraded", "degraded error");
}

async function testUnauthorized(): Promise<void> {
  installDbPool({});
  process.env.DASH_SESSION_SECRET = SECRET;
  const url = "http://127.0.0.1/api/v1/symbols/JKH.N0000/disclosures";
  const res = await disclosuresGet(new NextRequest(url, { method: "GET" }), {
    params: Promise.resolve({ symbol: "JKH.N0000" }),
  });
  assert(res.status === 401 || res.status === 403, `expected auth fail, got ${res.status}`);
}

async function main(): Promise<void> {
  process.env.DASH_SESSION_REVOKE_CHECK = "0";
  await testMapsBriefAndPdfFields();
  await testRejectsHostilePdfUrlAndHrefSchemes();
  await testBriefOnlyWhenReadyAndStripsControls();
  await testUnknownSymbol404();
  await testDbFailureDegrades();
  await testUnauthorized();
  console.log("WEB_DISCLOSURES_ROUTE_UNIT_OK");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
