"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { NfaStrip } from "@/components/market/NfaStrip";
import { PageHeader } from "@/components/layout/PageHeader";
import { buttonVariants } from "@/components/ui/button";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import {
  getMarketAlerts,
  getMarketFires,
  type MarketAlert,
  type MarketFire,
} from "@/lib/chime-market";
import { cn } from "@/lib/utils";

export default function MarketAlertsPage() {
  const { userId, loading: authLoading } = useCurrentUser();
  const [alerts, setAlerts] = useState<MarketAlert[]>([]);
  const [fires, setFires] = useState<MarketFire[]>([]);
  const [nfa, setNfa] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading || !userId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [a, f] = await Promise.all([getMarketAlerts(), getMarketFires()]);
        if (cancelled) return;
        setAlerts(a.items ?? []);
        setFires(f.items ?? []);
        setNfa(a.nfa || f.nfa);
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
        title="Alerts & fires"
        description="Chime rules and recent Telegram-ready fires. Open a fire to see cash context — not a trade ticket."
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

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-[1.25rem] border border-ceyfi-line bg-card p-4 dark:border-white/10">
          <h2 className="font-heading text-lg font-semibold">Active rules</h2>
          {loading ? (
            <p className="mt-3 text-sm text-muted-foreground">Loading…</p>
          ) : alerts.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">No active alerts.</p>
          ) : (
            <ul className="mt-3 divide-y divide-ceyfi-line/70 dark:divide-white/10">
              {alerts.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-2 py-2.5">
                  <div>
                    <p className="font-mono text-sm font-semibold">
                      {a.symbol.replace(/\.(N|X)0000$/i, "")}
                    </p>
                    <p className="text-[12px] text-muted-foreground">
                      {a.type}
                      {a.threshold != null ? ` · ${a.threshold}` : ""}
                    </p>
                  </div>
                  <span className="text-[11px] text-muted-foreground">
                    {a.active === false ? "paused" : "active"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-[1.25rem] border border-ceyfi-line bg-card p-4 dark:border-white/10">
          <h2 className="font-heading text-lg font-semibold">Fire history</h2>
          {loading ? (
            <p className="mt-3 text-sm text-muted-foreground">Loading…</p>
          ) : fires.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">No fires yet.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {fires.map((f) => (
                <li key={f.id}>
                  <Link
                    href={`/market/alerts/${encodeURIComponent(f.id)}`}
                    className="block rounded-xl border border-ceyfi-line/70 px-3 py-2.5 hover:bg-ceyfi-sprout/40 dark:border-white/10 dark:hover:bg-white/[0.04]"
                  >
                    <p className="font-mono text-sm font-semibold">
                      {(f.symbol || "").replace(/\.(N|X)0000$/i, "")}
                    </p>
                    <p className="text-[13px]">{f.title ?? f.message ?? f.type}</p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {f.fired_at?.slice(0, 16)?.replace("T", " ")}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
