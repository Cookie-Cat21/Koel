import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { ChangeBadge } from "@/components/kit/change-badge";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { PriceRefresh } from "@/components/price-refresh";
import { Button } from "@/components/ui/button";
import {
  UnwatchButton,
  WatchlistAddForm,
} from "@/components/watchlist-controls";
import {
  MAX_STOCK_NAME_LENGTH,
  MAX_STOCK_SECTOR_LENGTH,
  sanitizeDisclosureText,
} from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { serverApiGet } from "@/lib/api/server-fetch";
import { normalizeSymbol } from "@/lib/api/symbol";
import { toIso } from "@/lib/api/time";
import { requirePageSession } from "@/lib/auth/page-session";
import { formatNumber, formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Watchlist · Chime",
  description: "Symbols you watch for CSE price and disclosure alerts.",
};

type WatchlistPayload = {
  items: {
    symbol: string;
    name: string | null;
    sector: string | null;
    price: number | null;
    change: number | null;
    change_pct: number | null;
    ts: string | null;
  }[];
};

export default async function WatchlistPage() {
  await requirePageSession();

  const res = await serverApiGet("/api/v1/watchlist");
  let payload: WatchlistPayload | null = null;
  if (res.ok) {
    try {
      const body: unknown = await res.json();
      const itemsRaw =
        body && typeof body === "object" && !Array.isArray(body)
          ? (body as { items?: unknown }).items
          : null;
      if (Array.isArray(itemsRaw)) {
        const items: WatchlistPayload["items"] = [];
        for (const row of itemsRaw) {
          if (row == null || typeof row !== "object" || Array.isArray(row)) {
            continue;
          }
          const r = row as Record<string, unknown>;
          // Fail closed — only CSE SYMBOL_RE rows (not sanitize-only junk).
          const symbol = normalizeSymbol(
            typeof r.symbol === "string" ? r.symbol : null,
          );
          if (!symbol) continue;
          const price = toFiniteNumber(r.price);
          const change = toFiniteNumber(r.change);
          const change_pct = toFiniteNumber(r.change_pct);
          items.push({
            symbol,
            name: sanitizeDisclosureText(
              typeof r.name === "string" ? r.name : null,
              MAX_STOCK_NAME_LENGTH,
            ),
            sector: sanitizeDisclosureText(
              typeof r.sector === "string" ? r.sector : null,
              MAX_STOCK_SECTOR_LENGTH,
            ),
            price,
            change,
            change_pct,
            ts: toIso(r.ts),
          });
          // Cap parser — hostile / uncapped API JSON must not balloon SSR.
          if (items.length >= 500) break;
        }
        payload = { items };
      }
    } catch {
      payload = null;
    }
  }

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/watchlist" />
      <main id="main-content" tabIndex={-1} className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
        <PageHeader
          eyebrow="Watch"
          title="Watchlist"
          description="Symbols you watch for price and disclosure alerts. Pushes still go to Telegram."
          action={
            <PriceRefresh
              lastSnapshotAt={
                payload
                  ? payload.items
                      .map((i) => i.ts)
                      .filter((t): t is string => typeof t === "string" && !!t)
                      .sort()
                      .at(-1) ?? null
                  : null
              }
            />
          }
        />

        <div className="mt-6">
          <WatchlistAddForm />
        </div>

        {!payload ? (
          <EmptyState
            title="Couldn’t load watchlist"
            description={
              <>
                Chime couldn’t fetch your saved symbols just now. This is a
                load error, not an empty watchlist. Retry the request, or manage
                symbols with{" "}
                <code className="font-mono text-xs">/watch SYMBOL</code> in
                Telegram.
              </>
            }
            action={
              <Button asChild variant="outline">
                <a href="/watchlist">Retry loading watchlist</a>
              </Button>
            }
          />
        ) : payload.items.length === 0 ? (
          <EmptyState
            title="Your watchlist is empty"
            description={
              <>
                Add a CSE symbol with the form above to start watching prices
                and disclosures.{" "}
                <Link
                  href="/market"
                  className="rounded-sm underline underline-offset-4 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  Browse
                </Link>{" "}
                to discover tickers, or use{" "}
                <code className="font-mono text-xs">/watch SYMBOL</code> in
                Telegram — Chime keeps the list in sync either way. New symbols
                appear here after a poller tick, and Telegram{" "}
                <code className="font-mono text-xs">/watch</code> can seed the
                stocks table before the dashboard sees them.
              </>
            }
            action={
              <div className="flex flex-wrap gap-2">
                <Button asChild>
                  <Link href="/market">Browse</Link>
                </Button>
                <Button asChild variant="outline">
                  <a href="#watch_symbol">Add a symbol</a>
                </Button>
              </div>
            }
          />
        ) : (
          <>
            <div className="mt-8 hidden overflow-hidden rounded-lg border border-border/70 md:block">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Watchlist symbols</caption>
                <thead className="bg-muted/50 text-xs text-muted-foreground uppercase">
                  <tr>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Symbol
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Name
                    </th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">
                      Price
                    </th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">
                      Change%
                    </th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">
                      Updated
                    </th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {payload.items.map((item, idx) => (
                    <tr
                      key={item.symbol}
                      className={idx % 2 === 1 ? "bg-muted/25" : undefined}
                    >
                      <th scope="row" className="px-4 py-3 font-mono font-medium">
                        <Link
                          href={`/symbols/${encodeURIComponent(item.symbol)}`}
                          className="rounded-sm underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                        >
                          {item.symbol}
                        </Link>
                      </th>
                      <td className="max-w-xs px-4 py-3 text-muted-foreground">
                        <span className="block truncate" title={item.name ?? undefined}>
                          {item.name ?? "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums">
                        {formatNumber(item.price)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <ChangeBadge changePct={item.change_pct} />
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-muted-foreground">
                        {formatTs(item.ts)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end">
                          <UnwatchButton symbol={item.symbol} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="mt-8 divide-y divide-border/60 md:hidden">
              {payload.items.map((item) => (
                <li
                  key={item.symbol}
                  className="flex flex-col gap-3 py-4 first:pt-0"
                >
                  <div className="flex items-start justify-between gap-3">
                    <Link
                      href={`/symbols/${encodeURIComponent(item.symbol)}`}
                      className="group min-w-0 flex-1 rounded-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                      aria-label={`Open ${item.symbol} detail`}
                    >
                      <p className="font-mono text-sm font-medium group-hover:underline group-hover:underline-offset-4">
                        {item.symbol}
                      </p>
                      {item.name ? (
                        <p
                          className="truncate text-xs text-muted-foreground"
                          title={item.name}
                        >
                          {item.name}
                        </p>
                      ) : null}
                      <p className="mt-1 text-xs text-muted-foreground">
                        {formatTs(item.ts)}
                      </p>
                    </Link>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <span className="font-mono text-sm tabular-nums">
                        {formatNumber(item.price)}
                      </span>
                      <ChangeBadge changePct={item.change_pct} />
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <UnwatchButton symbol={item.symbol} />
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}

        <NfaInline className="mt-8" />
      </main>
      <NfaFooter />
    </div>
  );
}
