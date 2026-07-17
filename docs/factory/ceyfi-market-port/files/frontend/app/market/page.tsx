"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell, LineChart, List } from "lucide-react";

import { CashContextCard } from "@/components/market/CashContextCard";
import { NfaStrip } from "@/components/market/NfaStrip";
import { PageHeader } from "@/components/layout/PageHeader";
import { buttonVariants } from "@/components/ui/button";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { getFinancialSnapshot } from "@/lib/api";
import {
  getMarketOverview,
  type MarketAlert,
  type MarketFire,
  type MarketWatchItem,
} from "@/lib/chime-market";
import { cn, formatLKR } from "@/lib/utils";

export default function MarketPage() {
  const { userId, loading: authLoading } = useCurrentUser();
  const [watch, setWatch] = useState<MarketWatchItem[]>([]);
  const [alerts, setAlerts] = useState<MarketAlert[]>([]);
  const [fires, setFires] = useState<MarketFire[]>([]);
  const [nfa, setNfa] = useState<string>("");
  const [source, setSource] = useState<string>("mock");
  const [liquid, setLiquid] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading || !userId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [overview, snap] = await Promise.all([
          getMarketOverview(),
          getFinancialSnapshot(userId).catch(() => null),
        ]);
        if (cancelled) return;
        setWatch(overview.watchlist ?? []);
        setAlerts(overview.alerts ?? []);
        setFires(overview.fires ?? []);
        setNfa(overview.nfa);
        setSource(overview.source);
        if (snap) {
          setLiquid(
            Number(snap.current_balance ?? snap.balance_lkr ?? snap.savings_balance) ||
              null,
          );
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Market unavailable");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authLoading, userId]);

  return (
    <div data-module="market" className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6 lg:p-8">
      <PageHeader
        eyebrow="Market · powered by Chime"
        title="CSE watch & alerts"
        description="See names you care about and recent Chime pings next to your Ceyfi cash. You still trade with your licensed broker."
        action={
          <div className="flex flex-wrap gap-2">
            <Link
              href="/market/watchlist"
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            >
              <List className="mr-1.5 size-4" />
              Watchlist
            </Link>
            <Link
              href="/market/alerts"
              className={cn(buttonVariants({ size: "sm" }))}
            >
              <Bell className="mr-1.5 size-4" />
              Alerts
            </Link>
          </div>
        }
        meta={
          <p className="text-xs text-muted-foreground">
            Data source: {source === "chime" ? "Live Chime API" : "Demo mock (set CHIME_API_BASE to proxy)"}
          </p>
        }
      />

      <NfaStrip text={nfa || undefined} />

      {error ? (
        <p className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.8fr)]">
        <section className="space-y-4">
          <div className="rounded-[1.25rem] border border-ceyfi-line bg-card p-4 dark:border-white/10">
            <div className="mb-3 flex items-center gap-2">
              <LineChart className="size-4 text-ceyfi-green" aria-hidden />
              <h2 className="font-heading text-lg font-semibold">Watchlist</h2>
            </div>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : watch.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No watched symbols yet. Alerts attach to your Chime watchlist.
              </p>
            ) : (
              <ul className="divide-y divide-ceyfi-line/70 dark:divide-white/10">
                {watch.map((row) => (
                  <li
                    key={row.symbol}
                    className="flex items-center justify-between gap-3 py-2.5"
                  >
                    <div className="min-w-0">
                      <p className="font-mono text-sm font-semibold">
                        {row.symbol.replace(/\.(N|X)0000$/i, "")}
                      </p>
                      <p className="truncate text-[12px] text-muted-foreground">
                        {row.name ?? row.symbol}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-sm tabular-nums">
                        {row.price != null ? formatLKR(row.price) : "—"}
                      </p>
                      <p
                        className={
                          (row.change_pct ?? 0) >= 0
                            ? "font-mono text-[11px] text-emerald-700 dark:text-emerald-400"
                            : "font-mono text-[11px] text-red-600 dark:text-red-400"
                        }
                      >
                        {row.change_pct != null
                          ? `${row.change_pct > 0 ? "+" : ""}${row.change_pct.toFixed(2)}%`
                          : "—"}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-[1.25rem] border border-ceyfi-line bg-card p-4 dark:border-white/10">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 className="font-heading text-lg font-semibold">Recent fires</h2>
              <Link
                href="/market/alerts"
                className="text-xs font-medium text-ceyfi-green underline-offset-2 hover:underline"
              >
                All alerts
              </Link>
            </div>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : fires.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No recent Chime fires. Active rules: {alerts.length}.
              </p>
            ) : (
              <ul className="space-y-2">
                {fires.map((f) => (
                  <li key={f.id}>
                    <Link
                      href={`/market/alerts/${encodeURIComponent(f.id)}`}
                      className="block rounded-xl border border-ceyfi-line/70 px-3 py-2.5 transition-colors hover:bg-ceyfi-sprout/40 dark:border-white/10 dark:hover:bg-white/[0.04]"
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="font-mono text-sm font-semibold">
                          {(f.symbol || "").replace(/\.(N|X)0000$/i, "")}
                        </span>
                        <span className="text-[11px] text-muted-foreground">
                          {f.fired_at?.slice(0, 16)?.replace("T", " ") ?? ""}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[13px] text-foreground/90">
                        {f.title ?? f.message ?? f.type}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <CashContextCard liquidLkr={liquid} loading={loading} />
      </div>
    </div>
  );
}
