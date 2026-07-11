import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { NfaFooter } from "@/components/nfa-footer";
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
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10">
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          Watchlist
        </h1>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          Symbols you watch for price and disclosure alerts. Pushes still go to
          Telegram.
        </p>

        {!payload ? (
          <p className="mt-8 text-sm text-muted-foreground">
            Could not load watchlist right now.
          </p>
        ) : payload.items.length === 0 ? (
          <p className="mt-8 text-sm text-muted-foreground">
            No symbols yet — use{" "}
            <code className="font-mono text-xs">/watch</code> in Telegram, or
            add from Alerts once create lands.
          </p>
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
                <li key={item.symbol} className="py-4 first:pt-0">
                  <Link
                    href={`/symbols/${encodeURIComponent(item.symbol)}`}
                    className="group flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4"
                  >
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
                  </Link>
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
