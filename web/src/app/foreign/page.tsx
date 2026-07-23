import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { HelpLink } from "@/components/help-link";
import { AreaSpark } from "@/components/kit/area-spark";
import { KpiStrip } from "@/components/kit/kpi-strip";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { SoftPageRefresh } from "@/components/soft-page-refresh";
import { Button } from "@/components/ui/button";
import { queryTapePulse } from "@/lib/api/tape";
import { requirePageSession } from "@/lib/auth/page-session";
import { getPool } from "@/lib/db";
import { formatTs } from "@/lib/format";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Foreign net · koel",
  description:
    "CSE foreign equity purchase vs sales from daily market summary. Research only — not financial advice.",
};

function fmtLkr(n: number | null): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toFixed(0);
}

export default async function ForeignPage() {
  await requirePageSession();

  let tape: Awaited<ReturnType<typeof queryTapePulse>> | null = null;
  let loadError = false;
  try {
    tape = await queryTapePulse(getPool(), { foreignLimit: 90 });
  } catch {
    loadError = true;
  }

  const foreign = tape?.foreign ?? null;
  const history = tape?.foreign_history ?? [];
  const delta = tape?.foreign_delta ?? null;
  const nets = history.map((d) => d.foreign_net);
  const tone =
    foreign?.foreign_net == null
      ? "flat"
      : foreign.foreign_net > 0
        ? "up"
        : foreign.foreign_net < 0
          ? "down"
          : "flat";

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/context" />
      <SoftPageRefresh intervalMs={60_000} />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-4 py-8 sm:px-6 sm:py-10"
      >
        <PageHeader
          eyebrow="CSE tape · Research"
          title="Foreign net"
          description="Equity foreign purchase minus sales from CSE dailyMarketSummery rows koel accrued. Sign and size are research diagnostics — not a tip."
          action={
            <div className="flex flex-wrap items-center gap-2">
              <HelpLink topic="tape-pulse">Tape pulse help</HelpLink>
              <Button asChild variant="outline" size="sm">
                <Link href="/overview">Overview</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/book">Book pressure</Link>
              </Button>
            </div>
          }
        />

        {loadError ? (
          <EmptyState
            title="Could not load foreign flow"
            description="Database unavailable. Retry shortly."
          />
        ) : !foreign ? (
          <EmptyState
            title="No foreign sessions yet"
            description="Accrues when market-tick / ml-loop-nightly upserts market_daily_summary from CSE."
          />
        ) : (
          <>
            <section aria-labelledby="foreign-hero-heading" className="space-y-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Latest session · {foreign.trade_date}
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <h2
                  id="foreign-hero-heading"
                  className="font-display text-5xl font-semibold tracking-tight tabular-nums sm:text-6xl"
                >
                  {fmtLkr(foreign.foreign_net)}
                </h2>
                <span
                  className={cn(
                    "inline-flex rounded-md px-2.5 py-1 text-sm font-medium",
                    tone === "up" &&
                      "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300",
                    tone === "down" &&
                      "bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-300",
                    tone === "flat" && "bg-muted text-muted-foreground",
                  )}
                >
                  {foreign.foreign_net == null
                    ? "No net"
                    : foreign.foreign_net > 0
                      ? "Net buying"
                      : foreign.foreign_net < 0
                        ? "Net selling"
                        : "Flat"}
                </span>
              </div>
              <NfaInline />
            </section>

            <KpiStrip
              ariaLabel="Foreign flow summary"
              items={[
                {
                  id: "net",
                  label: "Foreign net",
                  value: fmtLkr(foreign.foreign_net),
                },
                {
                  id: "delta",
                  label: "Δ vs prior session",
                  value: delta != null ? `${fmtLkr(delta)}` : "—",
                },
                {
                  id: "buy",
                  label: "Foreign purchase",
                  value: fmtLkr(foreign.equity_foreign_purchase),
                },
                {
                  id: "sell",
                  label: "Foreign sales",
                  value: fmtLkr(foreign.equity_foreign_sales),
                },
                {
                  id: "turn",
                  label: "Turnover",
                  value: fmtLkr(foreign.volume_of_turnover),
                },
                {
                  id: "share",
                  label: "Of turnover",
                  value:
                    foreign.foreign_share_pct != null
                      ? `${foreign.foreign_share_pct.toFixed(1)}%`
                      : "—",
                },
              ]}
            />

            {nets.filter((v) => v != null).length >= 2 ? (
              <section
                aria-labelledby="foreign-history-heading"
                className="space-y-2 rounded-xl border border-border/70 bg-card px-4 py-4"
              >
                <h2
                  id="foreign-history-heading"
                  className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
                >
                  History · last {history.length} sessions
                </h2>
                <AreaSpark
                  values={nets}
                  labels={history.map((d) => d.trade_date)}
                  heightClass="h-36"
                  ariaLabel="Foreign net history"
                  interactive
                />
              </section>
            ) : null}

            <section
              aria-labelledby="foreign-table-heading"
              className="space-y-3"
            >
              <h2
                id="foreign-table-heading"
                className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
              >
                Recent sessions
              </h2>
              <div className="overflow-x-auto rounded-xl border border-border/70">
                <table className="w-full min-w-[36rem] text-left text-sm">
                  <thead className="border-b border-border/60 bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 font-medium">Date</th>
                      <th className="px-3 py-2 font-medium">Net</th>
                      <th className="px-3 py-2 font-medium">Purchase</th>
                      <th className="px-3 py-2 font-medium">Sales</th>
                      <th className="px-3 py-2 font-medium">Turnover</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...history].reverse().slice(0, 30).map((row) => (
                      <tr
                        key={row.trade_date}
                        className="border-b border-border/40 font-mono tabular-nums last:border-0"
                      >
                        <td className="px-3 py-2">{row.trade_date}</td>
                        <td className="px-3 py-2">{fmtLkr(row.foreign_net)}</td>
                        <td className="px-3 py-2">
                          {fmtLkr(row.equity_foreign_purchase)}
                        </td>
                        <td className="px-3 py-2">
                          {fmtLkr(row.equity_foreign_sales)}
                        </td>
                        <td className="px-3 py-2">
                          {fmtLkr(row.volume_of_turnover)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted-foreground">
                Soft-reloads about every minute. As of{" "}
                {formatTs(foreign.trade_date)}.
              </p>
            </section>
          </>
        )}

        <NfaFooter />
      </main>
    </div>
  );
}
