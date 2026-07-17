"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ExternalLink } from "lucide-react";

import { CashContextCard } from "@/components/market/CashContextCard";
import { NfaStrip } from "@/components/market/NfaStrip";
import { PageHeader } from "@/components/layout/PageHeader";
import { buttonVariants } from "@/components/ui/button";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { getFinancialSnapshot } from "@/lib/api";
import { getMarketFireDetail, type MarketFire } from "@/lib/chime-market";
import { cn, formatLKR } from "@/lib/utils";

export default function MarketAlertDetailPage() {
  const params = useParams<{ id: string }>();
  const fireId = decodeURIComponent(params.id ?? "");
  const { userId, loading: authLoading } = useCurrentUser();
  const [fire, setFire] = useState<MarketFire | null>(null);
  const [nfa, setNfa] = useState("");
  const [brokerHint, setBrokerHint] = useState("");
  const [liquid, setLiquid] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading || !userId || !fireId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [detail, snap] = await Promise.all([
          getMarketFireDetail(fireId),
          getFinancialSnapshot(userId).catch(() => null),
        ]);
        if (cancelled) return;
        setFire(detail.fire);
        setNfa(detail.nfa);
        setBrokerHint(detail.broker_cta?.hint ?? "");
        if (snap) {
          setLiquid(
            Number(snap.current_balance ?? snap.balance_lkr ?? snap.savings_balance) ||
              null,
          );
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Fire not found");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authLoading, userId, fireId]);

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6 lg:p-8">
      <PageHeader
        eyebrow="Alert fire"
        title={
          fire
            ? `${(fire.symbol || "").replace(/\.(N|X)0000$/i, "")} · ${fire.type}`
            : "Alert detail"
        }
        description="What moved (Chime) + whether your rupees are ready (Ceyfi). No order is placed here."
        action={
          <Link
            href="/market/alerts"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          >
            All alerts
          </Link>
        }
      />
      <NfaStrip text={nfa || undefined} />

      {error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-[1.25rem] border border-ceyfi-line bg-card p-5 dark:border-white/10">
          {loading || !fire ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="space-y-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Market signal
              </p>
              <h2 className="font-heading text-xl font-semibold">
                {fire.title ?? "Alert fired"}
              </h2>
              <p className="text-sm leading-relaxed text-foreground/90">
                {fire.message}
              </p>
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <div className="rounded-lg border border-ceyfi-line/70 px-3 py-2 dark:border-white/10">
                  <dt className="text-[11px] text-muted-foreground">Symbol</dt>
                  <dd className="font-mono font-semibold">{fire.symbol}</dd>
                </div>
                <div className="rounded-lg border border-ceyfi-line/70 px-3 py-2 dark:border-white/10">
                  <dt className="text-[11px] text-muted-foreground">Last price</dt>
                  <dd className="font-mono tabular-nums">
                    {fire.price != null ? formatLKR(fire.price) : "—"}
                  </dd>
                </div>
              </dl>
              <p className="text-[11px] text-muted-foreground">
                Fired {fire.fired_at?.replace("T", " ").replace("Z", " UTC")}
              </p>
            </div>
          )}
        </section>

        <div className="space-y-4">
          <CashContextCard liquidLkr={liquid} loading={loading} />
          <section className="rounded-[1.25rem] border border-dashed border-ceyfi-line bg-ceyfi-paper/50 p-4 dark:border-white/15 dark:bg-white/[0.03]">
            <p className="text-sm font-medium text-ceyfi-ink dark:text-white">
              Ready to act?
            </p>
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
              {brokerHint ||
                "Ceyfi does not place CSE orders. Use your licensed stockbroker."}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                href="/wallet"
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                Review wallet
              </Link>
              <span
                className={cn(
                  buttonVariants({ variant: "secondary", size: "sm" }),
                  "pointer-events-none inline-flex items-center gap-1.5 opacity-70",
                )}
                aria-disabled
              >
                Open my broker
                <ExternalLink className="size-3.5" aria-hidden />
              </span>
            </div>
            <p className="mt-2 text-[11px] text-muted-foreground">
              Broker handoff arrives in a later phase with a licensed partner —
              button stays disabled on purpose.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
