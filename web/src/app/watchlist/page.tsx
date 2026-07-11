import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Button } from "@/components/ui/button";
import {
  UnwatchButton,
  WatchlistAddForm,
} from "@/components/watchlist-controls";
import { serverApiGet } from "@/lib/api/server-fetch";
import { requirePageSession } from "@/lib/auth/page-session";
import { formatNumber, formatPct, formatTs } from "@/lib/format";

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
  const payload: WatchlistPayload | null = res.ok
    ? ((await res.json()) as WatchlistPayload)
    : null;

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/watchlist" />
      <main id="main-content" tabIndex={-1} className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          Watchlist
        </h1>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          Symbols you watch for price and disclosure alerts. Pushes still go to
          Telegram.
        </p>

        <WatchlistAddForm />

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
                and disclosures. Or use{" "}
                <code className="font-mono text-xs">/watch SYMBOL</code> in
                Telegram — Chime keeps the list in sync either way.
              </>
            }
            action={
              <Button asChild variant="outline">
                <a href="#watch_symbol">Add a symbol</a>
              </Button>
            }
          />
        ) : (
          <ul className="mt-8 divide-y divide-border/60">
            {payload.items.map((item) => {
              const pct = item.change_pct;
              const tone =
                pct == null
                  ? "text-muted-foreground"
                  : pct > 0
                    ? "text-[oklch(0.42_0.09_165)]"
                    : pct < 0
                      ? "text-destructive"
                      : "text-muted-foreground";
              return (
                <li
                  key={item.symbol}
                  className="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
                >
                  <Link
                    href={`/symbols/${encodeURIComponent(item.symbol)}`}
                    className="group min-w-0 flex-1 rounded-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                    aria-label={`Open ${item.symbol} detail`}
                  >
                    <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                      <div className="min-w-0">
                        <p className="font-mono text-sm font-medium group-hover:underline group-hover:underline-offset-4">
                          {item.symbol}
                        </p>
                        {item.name ? (
                          <p className="truncate text-xs text-muted-foreground">
                            {item.name}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 sm:justify-end">
                        <span className="font-mono text-sm">
                          {formatNumber(item.price)}
                        </span>
                        <span className={`font-mono text-sm ${tone}`}>
                          {formatPct(item.change_pct)}
                        </span>
                        <span className="w-full text-xs text-muted-foreground sm:w-auto">
                          {formatTs(item.ts)}
                        </span>
                      </div>
                    </div>
                  </Link>
                  <UnwatchButton symbol={item.symbol} />
                </li>
              );
            })}
          </ul>
        )}

        <NfaInline className="mt-8" />
      </main>
      <NfaFooter />
    </div>
  );
}
