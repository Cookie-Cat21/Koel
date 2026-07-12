import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Button } from "@/components/ui/button";
import {
  MAX_MARKET_Q_LENGTH,
  normalizeMarketQuery,
} from "@/lib/api/market-query";
import { serverApiGet } from "@/lib/api/server-fetch";
import { requirePageSession } from "@/lib/auth/page-session";
import { formatNumber, formatPct, formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Browse · Chime",
  description:
    "Thin CSE symbol browse from Chime snapshots — not a trading terminal.",
};

type MarketItem = {
  symbol: string;
  name: string | null;
  sector: string | null;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  ts: string | null;
};

/** Thin sector board row — name + change% only (not a screener). */
type SectorItem = {
  sector_id: number;
  name: string;
  change_pct: number | null;
};

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

function asMarketItems(body: unknown): MarketItem[] | null {
  if (body == null || typeof body !== "object") return null;
  const items = (body as { items?: unknown }).items;
  if (!Array.isArray(items)) return null;
  return items.filter(
    (row): row is MarketItem =>
      row != null &&
      typeof row === "object" &&
      typeof (row as MarketItem).symbol === "string" &&
      (row as MarketItem).symbol.length > 0,
  );
}

function asSectorItems(body: unknown): SectorItem[] | null {
  if (body == null || typeof body !== "object") return null;
  const items = (body as { items?: unknown }).items;
  if (!Array.isArray(items)) return null;
  const out: SectorItem[] = [];
  for (const row of items) {
    if (row == null || typeof row !== "object") continue;
    const r = row as Record<string, unknown>;
    const name = typeof r.name === "string" ? r.name.trim() : "";
    if (!name) continue;
    const sectorId = typeof r.sector_id === "number" ? r.sector_id : Number(r.sector_id);
    if (!Number.isFinite(sectorId)) continue;
    const pctRaw = r.change_pct;
    const change_pct =
      pctRaw == null
        ? null
        : typeof pctRaw === "number"
          ? pctRaw
          : Number(pctRaw);
    out.push({
      sector_id: sectorId,
      name,
      change_pct:
        change_pct != null && Number.isFinite(change_pct) ? change_pct : null,
    });
  }
  return out;
}

function MoversList({
  title,
  items,
  emptyLabel,
}: {
  title: string;
  items: MarketItem[];
  emptyLabel: string;
}) {
  return (
    <div className="min-w-0 flex-1">
      <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">{emptyLabel}</p>
      ) : (
        <ul className="mt-2 divide-y divide-border/60" aria-label={title}>
          {items.map((item) => {
            const pct = item.change_pct;
            const tone =
              pct == null
                ? "text-muted-foreground"
                : pct > 0
                  ? "text-[oklch(0.42_0.09_165)]"
                  : pct < 0
                    ? "text-[oklch(0.45_0.12_25)]"
                    : "text-muted-foreground";
            return (
              <li
                key={item.symbol}
                className="flex items-baseline justify-between gap-2 py-2"
              >
                <Link
                  href={`/symbols/${encodeURIComponent(item.symbol)}`}
                  className="rounded-sm font-mono text-sm font-medium text-foreground underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  {item.symbol}
                </Link>
                <span className={`font-mono text-sm tabular-nums ${tone}`}>
                  {formatPct(pct)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default async function MarketPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string | string[] }>;
}) {
  await requirePageSession();
  const sp = await searchParams;
  // Sanitize before any reflection (input defaultValue) or API round-trip.
  const q = normalizeMarketQuery(sp.q);
  const qs = new URLSearchParams({ limit: "100", sort: "change_pct" });
  if (q) qs.set("q", q);

  const [res, gainersRes, losersRes, sectorsRes] = await Promise.all([
    serverApiGet(`/api/v1/symbols?${qs.toString()}`),
    // Top movers / sectors only when not searching — keeps browse discovery thin.
    q
      ? Promise.resolve(null)
      : serverApiGet("/api/v1/market/movers?direction=up&limit=5"),
    q
      ? Promise.resolve(null)
      : serverApiGet("/api/v1/market/movers?direction=down&limit=5"),
    q ? Promise.resolve(null) : serverApiGet("/api/v1/sectors"),
  ]);

  const marketItems = await readJsonPayload(res, asMarketItems);
  const gainerItems = await readJsonPayload(gainersRes, asMarketItems);
  const loserItems = await readJsonPayload(losersRes, asMarketItems);
  const sectorItems = await readJsonPayload(sectorsRes, asSectorItems);
  const showMovers = !q && (gainerItems !== null || loserItems !== null);
  const showSectors = !q && sectorItems !== null;

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/market" />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          Browse
        </h1>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          CSE symbols from Chime&apos;s latest poller snapshots. Use this to find
          names to watch — alerts still fire on Telegram.
        </p>

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
          <Button type="submit" variant="outline">
            Search
          </Button>
        </form>

        <p className="mt-3">
          <NfaInline />
        </p>

        {showMovers ? (
          <section className="mt-8" aria-labelledby="top-movers-heading">
            <h2
              id="top-movers-heading"
              className="font-display text-lg font-semibold tracking-tight"
            >
              Top movers
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Largest daily % moves from the latest snapshots.
            </p>
            <div className="mt-4 flex flex-col gap-6 sm:flex-row sm:gap-10">
              <MoversList
                title="Gainers"
                items={gainerItems ?? []}
                emptyLabel="No gainers yet."
              />
              <MoversList
                title="Losers"
                items={loserItems ?? []}
                emptyLabel="No losers yet."
              />
            </div>
          </section>
        ) : null}

        {showSectors ? (
          <section className="mt-8" aria-labelledby="sectors-heading">
            <h2
              id="sectors-heading"
              className="font-display text-lg font-semibold tracking-tight"
            >
              Sectors
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              CSE sector index change from the latest poll — not a screener.
            </p>
            {(sectorItems ?? []).length === 0 ? (
              <p className="mt-3 text-sm text-muted-foreground">
                No sector data yet.
              </p>
            ) : (
              <ul
                className="mt-4 divide-y divide-border/60"
                aria-label="Sectors"
              >
                {(sectorItems ?? []).map((item) => {
                  const pct = item.change_pct;
                  const tone =
                    pct == null
                      ? "text-muted-foreground"
                      : pct > 0
                        ? "text-[oklch(0.42_0.09_165)]"
                        : pct < 0
                          ? "text-[oklch(0.45_0.12_25)]"
                          : "text-muted-foreground";
                  return (
                    <li
                      key={item.sector_id}
                      className="flex items-baseline justify-between gap-2 py-2"
                    >
                      <span className="min-w-0 truncate text-sm text-foreground">
                        {item.name}
                      </span>
                      <span
                        className={`shrink-0 font-mono text-sm tabular-nums ${tone}`}
                      >
                        {formatPct(pct)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        ) : null}

        {marketItems === null ? (
          <EmptyState
            title="Couldn’t load market list"
            description="Chime couldn’t read snapshot data just now. Retry in a moment, or check Health if this keeps happening."
            action={
              <Button asChild variant="outline">
                <Link href={q ? `/market?q=${encodeURIComponent(q)}` : "/market"}>
                  Retry
                </Link>
              </Button>
            }
          />
        ) : marketItems.length === 0 ? (
          <EmptyState
            title="No symbols yet"
            description={
              q
                ? "No symbols matched that search. Try another query, or browse again after the next market update."
                : "No snapshot data is available yet. Check back after market hours, or open Health if this persists."
            }
            action={
              q ? (
                <Button asChild variant="outline">
                  <Link href="/market">Clear search</Link>
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul
            className="mt-8 divide-y divide-border/60"
            aria-label="Market symbols"
          >
            {marketItems.map((item) => {
              const pct = item.change_pct;
              const tone =
                pct == null
                  ? "text-muted-foreground"
                  : pct > 0
                    ? "text-[oklch(0.42_0.09_165)]"
                    : pct < 0
                      ? "text-[oklch(0.45_0.12_25)]"
                      : "text-muted-foreground";
              return (
                <li
                  key={item.symbol}
                  className="flex flex-wrap items-baseline justify-between gap-2 py-3"
                >
                  <div className="min-w-0">
                    <Link
                      href={`/symbols/${encodeURIComponent(item.symbol)}`}
                      className="rounded-sm font-mono text-sm font-medium text-foreground underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                    >
                      {item.symbol}
                    </Link>
                    {item.name ? (
                      <p className="truncate text-sm text-muted-foreground">
                        {item.name}
                      </p>
                    ) : null}
                  </div>
                  <div className="text-right text-sm">
                    <p className="font-mono tabular-nums">
                      {formatNumber(item.price)}
                    </p>
                    <p className={`font-mono tabular-nums ${tone}`}>
                      {formatPct(pct)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatTs(item.ts)}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </main>
      <NfaFooter />
    </div>
  );
}
