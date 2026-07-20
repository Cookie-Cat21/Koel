import Link from "next/link";
import { redirect } from "next/navigation";

import { AppNav } from "@/components/app-nav";
import { HelpLink } from "@/components/help-link";
import { EmptyState } from "@/components/empty-state";
import { MoversBarList } from "@/components/kit/movers-bar-list";
import { SectorHeatStrip } from "@/components/kit/sector-heat-strip";
import { BrowseTable } from "@/components/market/browse-table";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { PriceRefresh } from "@/components/price-refresh";
import { Button } from "@/components/ui/button";
import {
  MAX_SECTOR_NAME_LENGTH,
  MAX_STOCK_NAME_LENGTH,
  MAX_STOCK_SECTOR_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import {
  MAX_MARKET_Q_LENGTH,
  firstSearchParam,
  normalizeMarketQuery,
} from "@/lib/api/market-query";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { toNonNegativeSafeInt, toSafePositiveInt } from "@/lib/api/safe-int";
import { serverApiGet } from "@/lib/api/server-fetch";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { optionalPageSession } from "@/lib/auth/page-session";

/** Exported for regression contract — used by movers a11y copy. */
export function changeDirectionSr(pct: number | null): string {
  if (pct == null) return "change unknown";
  if (pct > 0) return "up ";
  if (pct < 0) return "down ";
  return "unchanged ";
}

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Browse · koel",
  description: "CSE symbol browse from koel snapshots — pick what to watch.",
};

/** Page size for the symbol table section. */
const BROWSE_PAGE_SIZE = 50;
/** Cap market/movers rows parse — parity with symbols API max limit. */
const MAX_PAGE_MARKET_ITEMS = 200;
/** Cap sectors parse — parity with sectors API ``MAX_SECTORS``. */
const MAX_PAGE_SECTOR_ITEMS = 100;

type MarketItem = {
  symbol: string;
  name: string | null;
  sector: string | null;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  ts: string | null;
};

/** Thin sector board row — name + change% only. */
type SectorItem = {
  sector_id: number;
  name: string;
  change_pct: number | null;
};

type BrowsePayload = {
  items: MarketItem[];
  total: number | null;
};

function browseHref(
  q: string,
  page: number,
  opts: { sector?: string; hasEps?: boolean } = {},
): string {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (opts.sector) params.set("sector", opts.sector);
  if (opts.hasEps) params.set("has_eps", "1");
  if (page > 1) params.set("page", String(page));
  const s = params.toString();
  return s ? `/market?${s}` : "/market";
}

/** Fail closed on non-JSON / wrong shape so a bad movers body cannot 500 the page. */
async function readJsonPayload<T>(
  res: Response | null,
  pickItems: (body: unknown) => T | null,
): Promise<T | null> {
  if (!res || !res.ok) return null;
  try {
    const body: unknown = await res.json();
    return pickItems(body);
  } catch {
    return null;
  }
}

/**
 * Fail-closed browse rows: SYMBOL_RE symbols (no sanitize fallback), sanitize
 * name/sector, coerce numerics. Raw string change_pct must not reach formatPct.
 */
function asMarketItems(body: unknown): MarketItem[] | null {
  if (body == null || typeof body !== "object" || Array.isArray(body)) {
    return null;
  }
  const items = (body as { items?: unknown }).items;
  if (!Array.isArray(items)) return null;
  const out: MarketItem[] = [];
  for (const row of items) {
    if (out.length >= MAX_PAGE_MARKET_ITEMS) break;
    if (row == null || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    // Fail closed — only CSE SYMBOL_RE (no sanitize length-cap fallback).
    const symbol = normalizeSymbol(r.symbol);
    if (!symbol) continue;
    out.push({
      symbol,
      name: sanitizeDisclosureText(
        typeof r.name === "string" ? r.name : null,
        MAX_STOCK_NAME_LENGTH,
      ),
      sector: sanitizeDisclosureText(
        typeof r.sector === "string" ? r.sector : null,
        MAX_STOCK_SECTOR_LENGTH,
      ),
      price: toFiniteNumber(r.price),
      change: toFiniteNumber(r.change),
      change_pct: toFiniteNumber(r.change_pct),
      // Fail-closed ISO — no raw overlong / control-laden ts echo.
      ts: toIso(r.ts),
    });
  }
  return out;
}

function asBrowsePayload(body: unknown): BrowsePayload | null {
  const items = asMarketItems(body);
  if (items == null) return null;
  if (body == null || typeof body !== "object" || Array.isArray(body)) {
    return null;
  }
  const totalRaw = (body as { total?: unknown }).total;
  const total =
    totalRaw == null ? null : toNonNegativeSafeInt(totalRaw, -1);
  return {
    items,
    total: total != null && total >= 0 ? total : null,
  };
}

function asSectorItems(body: unknown): SectorItem[] | null {
  if (body == null || typeof body !== "object" || Array.isArray(body)) {
    return null;
  }
  const items = (body as { items?: unknown }).items;
  if (!Array.isArray(items)) return null;
  const out: SectorItem[] = [];
  for (const row of items) {
    if (out.length >= MAX_PAGE_SECTOR_ITEMS) break;
    if (row == null || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    const name =
      sanitizeDisclosureText(
        typeof r.name === "string" ? r.name : null,
        MAX_SECTOR_NAME_LENGTH,
      ) ?? "";
    if (!name) continue;
    // Digits-only SafeInteger — Number(oversized) used to precision-lose keys.
    const sectorId = toSafePositiveInt(r.sector_id);
    if (sectorId == null) continue;
    out.push({
      sector_id: sectorId,
      name,
      change_pct: toFiniteNumber(r.change_pct),
    });
  }
  return out;
}

function MoversList({
  title,
  headingId,
  items,
  emptyLabel,
}: {
  title: string;
  headingId: string;
  items: MarketItem[];
  emptyLabel: string;
}) {
  return (
    <div className="min-w-0 flex-1">
      <h3
        id={headingId}
        className="text-xs font-medium tracking-wide text-muted-foreground uppercase"
      >
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">{emptyLabel}</p>
      ) : (
        <MoversBarList
          items={items}
          className="mt-3"
          empty={emptyLabel}
        />
      )}
    </div>
  );
}

export default async function MarketPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string | string[];
    page?: string | string[];
    sector?: string | string[];
    has_eps?: string | string[];
  }>;
}) {
  const session = await optionalPageSession();
  const signedIn = session != null;
  const sp = await searchParams;
  // Sanitize before any reflection (input defaultValue) or API round-trip.
  const q = normalizeMarketQuery(sp.q);
  const sector =
    sanitizeDisclosureText(
      firstSearchParam(sp.sector),
      MAX_STOCK_SECTOR_LENGTH,
    ) ?? "";
  const hasEpsRaw = firstSearchParam(sp.has_eps);
  const hasEps =
    hasEpsRaw === "1" ||
    (typeof hasEpsRaw === "string" &&
      hasEpsRaw.trim().toLowerCase() === "true");
  const filterOpts = { sector: sector || undefined, hasEps };
  const pageParsed = toSafePositiveInt(firstSearchParam(sp.page));
  const page = pageParsed ?? 1;
  const offset = (page - 1) * BROWSE_PAGE_SIZE;

  const qs = new URLSearchParams({
    limit: String(BROWSE_PAGE_SIZE),
    offset: String(offset),
    sort: "change_pct",
  });
  if (q) qs.set("q", q);
  if (sector) qs.set("sector", sector);
  if (hasEps) qs.set("has_eps", "1");

  const browseOnly = Boolean(q || sector || hasEps);

  const [res, gainersRes, losersRes, sectorsRes] = await Promise.all([
    serverApiGet(`/api/v1/symbols?${qs.toString()}`),
    // Top movers / sectors only when not filtering — keeps browse discovery thin.
    browseOnly
      ? Promise.resolve(null)
      : serverApiGet("/api/v1/market/movers?direction=up&limit=5"),
    browseOnly
      ? Promise.resolve(null)
      : serverApiGet("/api/v1/market/movers?direction=down&limit=5"),
    // Always load sectors for chip filter (even when filtering).
    serverApiGet("/api/v1/sectors"),
  ]);

  const browse = await readJsonPayload(res, asBrowsePayload);
  const gainerItems = await readJsonPayload(gainersRes, asMarketItems);
  const loserItems = await readJsonPayload(losersRes, asMarketItems);
  const sectorItems = await readJsonPayload(sectorsRes, asSectorItems);

  const marketItems = browse?.items ?? null;
  const total = browse?.total ?? null;
  const totalPages =
    total != null && total > 0
      ? Math.max(1, Math.ceil(total / BROWSE_PAGE_SIZE))
      : null;

  // Out-of-range page → first page (preserve search).
  if (totalPages != null && page > totalPages) {
    redirect(browseHref(q, 1, filterOpts));
  }

  const rangeStart =
    marketItems && marketItems.length > 0 ? offset + 1 : 0;
  const rangeEnd =
    marketItems && marketItems.length > 0
      ? offset + marketItems.length
      : 0;
  const hasPrev = page > 1;
  const hasNext =
    totalPages != null
      ? page < totalPages
      : (marketItems?.length ?? 0) >= BROWSE_PAGE_SIZE;

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      {signedIn ? <AppNav active="/market" /> : <MarketingNav />}
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        <PageHeader
          eyebrow="Market"
          title="Browse"
          description="CSE symbols from koel’s latest poller snapshots. Find names to watch — Telegram still delivers the push when your rules fire."
          action={
            <div className="flex flex-wrap items-center gap-2">
              <HelpLink topic="market-browse">Browse help</HelpLink>
              <PriceRefresh
                lastSnapshotAt={
                  (marketItems ?? [])
                    .map((i) => i.ts)
                    .filter((t): t is string => typeof t === "string" && !!t)
                    .sort()
                    .at(-1) ?? null
                }
              />
            </div>
          }
        />
        {!signedIn ? (
          <p className="mt-3 text-sm text-muted-foreground" role="status">
            Public browse —{" "}
            <Link
              href="/login"
              className="underline underline-offset-4 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              sign in
            </Link>{" "}
            to add watchlist items and alert rules.
          </p>
        ) : null}

        <form
          className="mt-6 flex flex-wrap gap-2"
          method="get"
          action="/market"
          role="search"
        >
          <label className="sr-only" htmlFor="market_q">
            Search symbols by ticker or name
          </label>
          <input
            id="market_q"
            name="q"
            type="search"
            defaultValue={q}
            maxLength={MAX_MARKET_Q_LENGTH}
            autoComplete="off"
            spellCheck={false}
            placeholder="Symbol or name"
            className="min-w-[12rem] flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          />
          {sector ? (
            <input type="hidden" name="sector" value={sector} />
          ) : null}
          {hasEps ? <input type="hidden" name="has_eps" value="1" /> : null}
          <Button type="submit" variant="outline">
            Search
          </Button>
        </form>

        <div
          className="mt-4 flex flex-wrap items-center gap-2"
          aria-label="Light browse filters"
        >
          <Link
            href={browseHref(q, 1, { hasEps })}
            className={`rounded-md border px-2.5 py-1 text-xs transition-colors focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none ${
              !sector
                ? "border-foreground/30 bg-foreground/5 text-foreground"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            All sectors
          </Link>
          {(sectorItems ?? []).slice(0, 12).map((item) => {
            const active =
              sector.length > 0 &&
              sector.toUpperCase() === item.name.toUpperCase();
            return (
              <Link
                key={item.sector_id}
                href={browseHref(q, 1, {
                  sector: item.name,
                  hasEps,
                })}
                className={`max-w-[12rem] truncate rounded-md border px-2.5 py-1 text-xs transition-colors focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none ${
                  active
                    ? "border-foreground/30 bg-foreground/5 text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
                title={item.name}
              >
                {item.name}
              </Link>
            );
          })}
          <Link
            href={browseHref(q, 1, {
              sector: sector || undefined,
              hasEps: !hasEps,
            })}
            className={`rounded-md border px-2.5 py-1 text-xs transition-colors focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none ${
              hasEps
                ? "border-foreground/30 bg-foreground/5 text-foreground"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            Has EPS
          </Link>
        </div>

        <p className="mt-3">
          <NfaInline />
        </p>

        {!browseOnly && gainerItems !== null && loserItems !== null ? (
          <section className="mt-8" aria-labelledby="top-movers-heading">
            <h2
              id="top-movers-heading"
              className="font-display text-lg font-semibold tracking-tight"
            >
              Top movers
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Largest daily % moves from the latest snapshots.{" "}
              {signedIn ? (
                <Link
                  href="/watchlist"
                  className="underline underline-offset-4 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  Add via watchlist
                </Link>
              ) : (
                <Link
                  href="/login"
                  className="underline underline-offset-4 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  Sign in to watchlist
                </Link>
              )}
              .
            </p>
            <div className="mt-4 flex flex-col gap-6 sm:flex-row sm:gap-10">
              <MoversList
                title="Gainers"
                headingId="movers-gainers-heading"
                items={gainerItems}
                emptyLabel="No gainers yet."
              />
              <MoversList
                title="Losers"
                headingId="movers-losers-heading"
                items={loserItems}
                emptyLabel="No losers yet."
              />
            </div>
          </section>
        ) : null}

        {!browseOnly && sectorItems !== null ? (
          <section className="mt-8" aria-labelledby="sectors-heading">
            <h2
              id="sectors-heading"
              className="font-display text-lg font-semibold tracking-tight"
            >
              Sectors
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              CSE sector index change from the latest poll — soft heat strip,
              not a trading terminal board. Use the chips above to filter the
              table.
            </p>
            <div className="mt-4">
              <SectorHeatStrip items={sectorItems} />
            </div>
          </section>
        ) : null}

        {marketItems === null ? (
          <EmptyState
            title="Couldn’t load market list"
            description="koel couldn’t read snapshot data just now. Retry in a moment, or check Health if this keeps happening."
            action={
              <Button asChild variant="outline">
                <Link href={browseHref(q, page, filterOpts)}>Retry</Link>
              </Button>
            }
          />
        ) : marketItems.length === 0 ? (
          <EmptyState
            title="No symbols yet"
            description={
              browseOnly
                ? "No symbols matched that filter. Clear search or sector / Has EPS chips, or browse again after the next market update."
                : "No snapshot data yet. On the host, run make tick (or leave poller/both running) to seed browse, then refresh. Open Health if this persists."
            }
            action={
              browseOnly ? (
                <Button asChild variant="outline">
                  <Link href="/market">Clear filters</Link>
                </Button>
              ) : undefined
            }
          />
        ) : (
          <section aria-labelledby="all-symbols-heading">
            <div className="mt-8 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2
                  id="all-symbols-heading"
                  className="font-display text-lg font-semibold tracking-tight"
                >
                  All symbols
                </h2>
                <p className="mt-1 text-sm text-muted-foreground" role="status">
                  {total != null
                    ? `Showing ${rangeStart}–${rangeEnd} of ${total}`
                    : `Showing ${rangeStart}–${rangeEnd}`}
                  {totalPages != null && totalPages > 1
                    ? ` · Page ${page} of ${totalPages}`
                    : null}
                </p>
              </div>
              {hasPrev || hasNext ? (
                <nav
                  className="flex items-center gap-2"
                  aria-label="Symbol list pages"
                >
                  {hasPrev ? (
                    <Button asChild variant="outline" size="sm">
                      <Link href={browseHref(q, page - 1, filterOpts)} rel="prev">
                        Previous
                      </Link>
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" disabled>
                      Previous
                    </Button>
                  )}
                  {hasNext ? (
                    <Button asChild variant="outline" size="sm">
                      <Link href={browseHref(q, page + 1, filterOpts)} rel="next">
                        Next
                      </Link>
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" disabled>
                      Next
                    </Button>
                  )}
                </nav>
              ) : null}
            </div>
            <BrowseTable items={marketItems} />
            {hasPrev || hasNext ? (
              <nav
                className="mt-4 flex items-center justify-between gap-2"
                aria-label="Symbol list pages (footer)"
              >
                <p className="text-sm text-muted-foreground">
                  {total != null
                    ? `${rangeStart}–${rangeEnd} of ${total}`
                    : `${rangeStart}–${rangeEnd}`}
                </p>
                <div className="flex items-center gap-2">
                  {hasPrev ? (
                    <Button asChild variant="outline" size="sm">
                      <Link href={browseHref(q, page - 1, filterOpts)} rel="prev">
                        Previous
                      </Link>
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" disabled>
                      Previous
                    </Button>
                  )}
                  {hasNext ? (
                    <Button asChild variant="outline" size="sm">
                      <Link href={browseHref(q, page + 1, filterOpts)} rel="next">
                        Next
                      </Link>
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" disabled>
                      Next
                    </Button>
                  )}
                </div>
              </nav>
            ) : null}
          </section>
        )}
      </main>
      <NfaFooter />
    </div>
  );
}
