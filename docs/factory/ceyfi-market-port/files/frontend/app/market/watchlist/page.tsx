"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { NfaStrip } from "@/components/market/NfaStrip";
import { PageHeader } from "@/components/layout/PageHeader";
import { buttonVariants } from "@/components/ui/button";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { getMarketWatchlist, type MarketWatchItem } from "@/lib/chime-market";
import { cn, formatLKR } from "@/lib/utils";

export default function MarketWatchlistPage() {
  const { userId, loading: authLoading } = useCurrentUser();
  const [items, setItems] = useState<MarketWatchItem[]>([]);
  const [nfa, setNfa] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading || !userId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await getMarketWatchlist();
        if (cancelled) return;
        setItems(data.items ?? []);
        setNfa(data.nfa);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authLoading, userId]);

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6 lg:p-8">
      <PageHeader
        eyebrow="Market"
        title="Watchlist"
        description="Symbols mirrored from Chime. Manage rules in Alerts — Ceyfi does not scrape cse.lk."
        action={
          <Link
            href="/market"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          >
            Back to Market
          </Link>
        }
      />
      <NfaStrip text={nfa || undefined} />
      <div className="overflow-hidden rounded-[1.25rem] border border-ceyfi-line bg-card dark:border-white/10">
        <div className="grid grid-cols-[minmax(0,1fr)_6rem_5rem] gap-2 border-b border-ceyfi-line px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground dark:border-white/10">
          <span>Symbol</span>
          <span className="text-right">Price</span>
          <span className="text-right">Chg</span>
        </div>
        {loading ? (
          <p className="px-4 py-8 text-sm text-muted-foreground">Loading…</p>
        ) : items.length === 0 ? (
          <p className="px-4 py-8 text-sm text-muted-foreground">No watched symbols.</p>
        ) : (
          <ul className="divide-y divide-ceyfi-line/70 dark:divide-white/10">
            {items.map((row) => (
              <li
                key={row.symbol}
                className="grid grid-cols-[minmax(0,1fr)_6rem_5rem] items-center gap-2 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="font-mono text-sm font-semibold">
                    {row.symbol.replace(/\.(N|X)0000$/i, "")}
                  </p>
                  <p className="truncate text-[12px] text-muted-foreground">
                    {row.name ?? row.symbol}
                  </p>
                </div>
                <p className="text-right font-mono text-sm tabular-nums">
                  {row.price != null ? formatLKR(row.price) : "—"}
                </p>
                <p className="text-right font-mono text-sm tabular-nums">
                  {row.change_pct != null
                    ? `${row.change_pct > 0 ? "+" : ""}${row.change_pct.toFixed(2)}%`
                    : "—"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
