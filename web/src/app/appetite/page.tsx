import Link from "next/link";

import { AppetiteComponents } from "@/components/appetite/appetite-components";
import { AppetiteHistoryChart } from "@/components/appetite/appetite-history-chart";
import {
  AppetiteBandBadge,
  AppetiteMeter,
} from "@/components/appetite/appetite-meter";
import { AppetiteTracker } from "@/components/appetite/appetite-tracker";
import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { KpiStrip } from "@/components/kit/kpi-strip";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import {
  daysInCurrentBand,
  deltaVs,
  headlineDay,
  headlineIndex,
  queryAppetiteHistory,
} from "@/lib/api/appetite";
import { requirePageSession } from "@/lib/auth/page-session";
import { getPool } from "@/lib/db";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Market Appetite · koel",
  description:
    "CSE market appetite research score from breadth, intensity, ASPI, and participation. Not financial advice.",
};

function fmtDelta(d: number | null): string {
  if (d == null || !Number.isFinite(d)) return "—";
  const r = Math.round(d * 10) / 10;
  return `${r > 0 ? "+" : ""}${r.toFixed(1)}`;
}

export default async function AppetitePage() {
  await requirePageSession();

  let history: Awaited<ReturnType<typeof queryAppetiteHistory>> = [];
  let loadError = false;
  try {
    history = await queryAppetiteHistory(getPool(), {
      limit: 252,
      source: "cse",
    });
  } catch {
    loadError = true;
  }

  const hi = headlineIndex(history);
  const latest = headlineDay(history);
  const d1 = deltaVs(history, 1, hi);
  const d5 = deltaVs(history, 5, hi);
  const d21 = deltaVs(history, 21, hi);
  const inBand = daysInCurrentBand(history, hi);
  const thinSkipped =
    history.length > 0 &&
    hi >= 0 &&
    hi < history.length - 1 &&
    history[history.length - 1]!.universe_n < 100;

  return (
    <div className="min-h-screen bg-background">
      <AppNav active="/appetite" />
      <main className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6">
        <PageHeader
          eyebrow="koel · Research"
          title="Market Appetite"
          description="Session mood proxy from CSE breadth, move intensity, ASPI day change, and participation. Higher scores are not a tip — research only."
          action={
            <Button asChild variant="outline" size="sm">
              <Link href="/overview">Overview</Link>
            </Button>
          }
        />

        {loadError ? (
          <EmptyState
            title="Could not load appetite"
            description="Database unavailable. Retry shortly."
          />
        ) : !latest ? (
          <EmptyState
            title="No appetite history yet"
            description="Run python3 -m chime appetite-backfill after path-backfill fills daily_bars."
          />
        ) : (
          <>
            <section aria-labelledby="appetite-hero-heading" className="space-y-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h2 id="appetite-hero-heading" className="sr-only">
                    Current appetite
                  </h2>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                    Headline session · {latest.trade_date}
                    {thinSkipped
                      ? " · newest thin day skipped for headline"
                      : null}
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-3">
                    <span className="font-mono text-5xl font-semibold tabular-nums tracking-tight sm:text-6xl">
                      {Math.round(latest.score)}
                    </span>
                    <AppetiteBandBadge
                      band={latest.band}
                      className="text-base sm:text-lg"
                    />
                  </div>
                  <div className="mt-2">
                    <NfaInline />
                  </div>
                </div>
              </div>
              <AppetiteMeter
                score={latest.score}
                band={latest.band}
                size="lg"
              />
            </section>

            <KpiStrip
              ariaLabel="Appetite summary"
              items={[
                {
                  id: "score",
                  label: "Score",
                  value: String(Math.round(latest.score)),
                  hint: latest.band.replaceAll("_", " "),
                },
                {
                  id: "d1",
                  label: "Δ 1 session",
                  value: fmtDelta(d1),
                },
                {
                  id: "d5",
                  label: "Δ 5 sessions",
                  value: fmtDelta(d5),
                },
                {
                  id: "d21",
                  label: "Δ ~1 month",
                  value: fmtDelta(d21),
                },
                {
                  id: "band-days",
                  label: "Days in band",
                  value: String(inBand),
                },
                {
                  id: "univ",
                  label: "Universe",
                  value: String(latest.universe_n),
                  hint:
                    latest.advancers != null && latest.decliners != null
                      ? `${latest.advancers}↑ / ${latest.decliners}↓`
                      : undefined,
                },
              ]}
            />

            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
              <section aria-labelledby="appetite-history-heading" className="space-y-2">
                <h2
                  id="appetite-history-heading"
                  className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
                >
                  History (CSE path · ~1y)
                </h2>
                <AppetiteHistoryChart historyAsc={history} />
              </section>
              <section aria-labelledby="appetite-components-heading" className="space-y-2">
                <h2
                  id="appetite-components-heading"
                  className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
                >
                  Components
                </h2>
                <AppetiteComponents components={latest.components} />
                {latest.aspi_change_pct == null ? (
                  <p className="text-[11px] text-muted-foreground">
                    ASPI day change missing for this session — index component
                    held near neutral.
                  </p>
                ) : (
                  <p className="font-mono text-[11px] tabular-nums text-muted-foreground">
                    ASPI {latest.aspi_change_pct >= 0 ? "+" : ""}
                    {latest.aspi_change_pct.toFixed(2)}%
                  </p>
                )}
              </section>
            </div>

            <section aria-labelledby="appetite-tracker-heading" className="space-y-2">
              <h2
                id="appetite-tracker-heading"
                className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
              >
                Band chronology
              </h2>
              <AppetiteTracker historyAsc={history} limit={90} />
            </section>

            <section
              aria-labelledby="appetite-method-heading"
              className="rounded-lg border border-border/70 bg-muted/10 px-4 py-3 text-sm text-muted-foreground"
            >
              <h2
                id="appetite-method-heading"
                className="text-sm font-medium text-foreground"
              >
                How this is built
              </h2>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                <li>
                  <span className="text-foreground">Breadth 40%</span> — share of
                  listed names up on the session
                </li>
                <li>
                  <span className="text-foreground">Intensity 25%</span> — among
                  moves ≥2%, share that are up
                </li>
                <li>
                  <span className="text-foreground">Index 20%</span> — ASPI day
                  change mapped ±3% → 0–100
                </li>
                <li>
                  <span className="text-foreground">Participation 15%</span> —
                  turnover / volume participation
                </li>
              </ul>
              <p className="mt-2 text-xs">
                CSE-truth window is ~1 year of daily bars. Partial sessions
                (thin universe) are kept in history but skipped for the
                headline. Yahoo hybrid long history stays research-flagged and
                is not shown here by default.
              </p>
            </section>
          </>
        )}

        <NfaFooter />
      </main>
    </div>
  );
}
