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
import {
  queryBookPressureSeries,
  queryTapePulse,
  type BookPressure,
} from "@/lib/api/tape";
import { requirePageSession } from "@/lib/auth/page-session";
import { getPool } from "@/lib/db";
import { formatTs } from "@/lib/format";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Book pressure · koel",
  description:
    "Public CSE bid/ask totals sample across watched and top-volume names. Not licensed L2 depth. Not financial advice.",
};

function bookHeadline(book: BookPressure): string {
  if (book.label === "bid_heavy") return "Bid heavy";
  if (book.label === "ask_heavy") return "Ask heavy";
  if (book.label === "balanced") return "Balanced";
  return "—";
}

function BookBar({ book }: { book: BookPressure }) {
  const bid = book.bid_share_pct;
  if (bid == null || !Number.isFinite(bid)) {
    return (
      <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full w-1/2 bg-muted-foreground/25" />
      </div>
    );
  }
  const pct = Math.max(0, Math.min(100, bid));
  return (
    <div className="space-y-2">
      <div
        className="relative h-3 w-full overflow-hidden rounded-full bg-rose-200/80 dark:bg-rose-950/50"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        aria-label={`Bid share ${pct.toFixed(0)} percent`}
      >
        <div
          className="h-full bg-emerald-600/85"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between font-mono text-xs tabular-nums text-muted-foreground">
        <span>Bid {pct.toFixed(1)}%</span>
        <span>Ask {(100 - pct).toFixed(1)}%</span>
      </div>
    </div>
  );
}

export default async function BookPressurePage() {
  await requirePageSession();
  const pool = getPool();

  let tape: Awaited<ReturnType<typeof queryTapePulse>> | null = null;
  let series: Awaited<ReturnType<typeof queryBookPressureSeries>> = [];
  let loadError = false;
  try {
    [tape, series] = await Promise.all([
      queryTapePulse(pool),
      queryBookPressureSeries(pool, { lookbackMinutes: 48 * 60, maxPoints: 64 }),
    ]);
  } catch {
    loadError = true;
  }

  const book =
    tape?.book ??
    ({
      imbalance_pct: null,
      bid_share_pct: null,
      sample_n: 0,
      as_of: null,
      label: "unknown",
    } satisfies BookPressure);

  const imbShares = series.map((p) => p.imbalance_pct);
  const bidShares = series.map((p) => p.bid_share_pct);

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
          title="Book pressure"
          description="Market-wide public bid vs ask totals from CSE /orderBook samples koel accrues each market-tick. Not licensed Level-2 depth — research only."
          action={
            <div className="flex flex-wrap items-center gap-2">
              <HelpLink topic="tape-pulse">Tape pulse help</HelpLink>
              <Button asChild variant="outline" size="sm">
                <Link href="/overview">Overview</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/foreign">Foreign net</Link>
              </Button>
            </div>
          }
        />

        {loadError ? (
          <EmptyState
            title="Could not load book pressure"
            description="Database unavailable. Retry shortly."
          />
        ) : book.sample_n <= 0 ? (
          <EmptyState
            title="No public book sample yet"
            description="Samples land when market-tick polls /orderBook for top volume ∪ watchlist (ORDER_BOOK_SAMPLE_SIZE)."
          />
        ) : (
          <>
            <section aria-labelledby="book-hero-heading" className="space-y-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Latest sample
                {book.as_of ? ` · ${formatTs(book.as_of)}` : null}
              </p>
              <div className="flex flex-wrap items-baseline gap-3">
                <h2
                  id="book-hero-heading"
                  className="font-display text-5xl font-semibold tracking-tight sm:text-6xl"
                >
                  {bookHeadline(book)}
                </h2>
                <span
                  className={cn(
                    "inline-flex rounded-md px-2.5 py-1 font-mono text-sm tabular-nums",
                    (book.imbalance_pct ?? 0) > 0
                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300"
                      : (book.imbalance_pct ?? 0) < 0
                        ? "bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-300"
                        : "bg-muted text-muted-foreground",
                  )}
                >
                  {book.imbalance_pct == null
                    ? "—"
                    : `${book.imbalance_pct > 0 ? "+" : ""}${book.imbalance_pct.toFixed(1)}% imb`}
                </span>
              </div>
              <BookBar book={book} />
              <NfaInline />
            </section>

            <KpiStrip
              ariaLabel="Book pressure summary"
              items={[
                {
                  id: "label",
                  label: "Regime",
                  value: bookHeadline(book),
                },
                {
                  id: "bid",
                  label: "Bid share",
                  value:
                    book.bid_share_pct != null
                      ? `${book.bid_share_pct.toFixed(1)}%`
                      : "—",
                },
                {
                  id: "ask",
                  label: "Ask share",
                  value:
                    book.bid_share_pct != null
                      ? `${(100 - book.bid_share_pct).toFixed(1)}%`
                      : "—",
                },
                {
                  id: "imb",
                  label: "Imbalance",
                  value:
                    book.imbalance_pct != null
                      ? `${book.imbalance_pct > 0 ? "+" : ""}${book.imbalance_pct.toFixed(1)}%`
                      : "—",
                },
                {
                  id: "n",
                  label: "Symbols sampled",
                  value: String(book.sample_n),
                },
              ]}
            />

            {series.length >= 2 ? (
              <div className="grid gap-4 lg:grid-cols-2">
                <section
                  aria-labelledby="book-imb-spark-heading"
                  className="space-y-2 rounded-xl border border-border/70 bg-card px-4 py-4"
                >
                  <h2
                    id="book-imb-spark-heading"
                    className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
                  >
                    Imbalance · ~15m buckets
                  </h2>
                  <AreaSpark
                    values={imbShares}
                    labels={series.map((p) => formatTs(p.as_of))}
                    heightClass="h-32"
                    ariaLabel="Book imbalance history"
                    interactive
                  />
                </section>
                <section
                  aria-labelledby="book-bid-spark-heading"
                  className="space-y-2 rounded-xl border border-border/70 bg-card px-4 py-4"
                >
                  <h2
                    id="book-bid-spark-heading"
                    className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
                  >
                    Bid share %
                  </h2>
                  <AreaSpark
                    values={bidShares}
                    labels={series.map((p) => formatTs(p.as_of))}
                    tone="neutral"
                    heightClass="h-32"
                    ariaLabel="Bid share history"
                    interactive
                  />
                </section>
              </div>
            ) : null}

            {series.length > 0 ? (
              <section
                aria-labelledby="book-table-heading"
                className="space-y-3"
              >
                <h2
                  id="book-table-heading"
                  className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
                >
                  Recent sample windows
                </h2>
                <div className="overflow-x-auto rounded-xl border border-border/70">
                  <table className="w-full min-w-[28rem] text-left text-sm">
                    <thead className="border-b border-border/60 bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                      <tr>
                        <th className="px-3 py-2 font-medium">As of</th>
                        <th className="px-3 py-2 font-medium">Symbols</th>
                        <th className="px-3 py-2 font-medium">Bid %</th>
                        <th className="px-3 py-2 font-medium">Imb %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...series].reverse().slice(0, 24).map((row) => (
                        <tr
                          key={row.as_of}
                          className="border-b border-border/40 font-mono tabular-nums last:border-0"
                        >
                          <td className="px-3 py-2">{formatTs(row.as_of)}</td>
                          <td className="px-3 py-2">{row.sample_n}</td>
                          <td className="px-3 py-2">
                            {row.bid_share_pct.toFixed(1)}
                          </td>
                          <td className="px-3 py-2">
                            {row.imbalance_pct > 0 ? "+" : ""}
                            {row.imbalance_pct.toFixed(1)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-muted-foreground">
                  Public totals only — not a licensed L2 book. Soft-reloads
                  about every minute.
                </p>
              </section>
            ) : null}
          </>
        )}

        <NfaFooter />
      </main>
    </div>
  );
}
