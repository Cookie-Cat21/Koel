import Link from "next/link";
import type { ReactNode } from "react";

import {
  AppetiteBandBadge,
  AppetiteMeter,
} from "@/components/appetite/appetite-meter";
import { AppetiteTracker } from "@/components/appetite/appetite-tracker";
import { AreaSpark } from "@/components/kit/area-spark";
import { NfaInline } from "@/components/nfa-inline";
import {
  BAND_LABEL,
  type AppetiteDay,
} from "@/lib/api/appetite";
import type { BookPressure, ForeignDay } from "@/lib/api/tape";
import { cn } from "@/lib/utils";

function fmtLkr(n: number | null): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toFixed(0);
}

function fmtDelta(d: number | null): string {
  if (d == null || !Number.isFinite(d)) return "—";
  const r = Math.round(d * 10) / 10;
  return `${r > 0 ? "+" : ""}${r.toFixed(1)}`;
}

function Chip({
  label,
  value,
  detail,
  delta,
  deltaTone,
  status,
  children,
  spark,
  href,
  className,
}: {
  label: string;
  value: string;
  detail: string;
  delta?: string;
  deltaTone?: "up" | "down" | "flat";
  status?: ReactNode;
  children?: ReactNode;
  spark?: ReactNode;
  /** When set, the whole chip navigates to a detail page. */
  href?: string;
  className?: string;
}) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {label}
        </p>
        <div className="flex shrink-0 items-center gap-1.5">
          {delta ? (
            <span
              className={cn(
                "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[10px] tabular-nums",
                deltaTone === "up" &&
                  "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300",
                deltaTone === "down" &&
                  "bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-300",
                (deltaTone === "flat" || !deltaTone) &&
                  "bg-muted text-muted-foreground",
              )}
            >
              {delta}
            </span>
          ) : null}
          {href ? (
            <span
              aria-hidden
              className="text-[10px] font-medium text-muted-foreground transition-colors group-hover:text-foreground"
            >
              →
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <p className="font-display text-3xl font-semibold tracking-tight tabular-nums">
          {value}
        </p>
        {status}
      </div>

      <p className="mt-1 font-mono text-[11px] leading-snug tabular-nums text-muted-foreground">
        {detail}
      </p>

      {children ? <div className="mt-3">{children}</div> : null}

      {spark ? (
        <div className="mt-auto border-t border-border/50 pt-2.5">{spark}</div>
      ) : (
        <div className="mt-auto" />
      )}
    </>
  );

  const shell = cn(
    "group flex min-h-[11.5rem] min-w-0 flex-1 flex-col rounded-lg border border-border/70 bg-background px-3.5 py-3.5 shadow-[0_1px_0_oklch(0.9_0.006_250_/_0.6)]",
    href &&
      "transition-colors hover:border-foreground/30 hover:bg-muted/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    className,
  );

  if (href) {
    return (
      <Link
        href={href}
        className={shell}
        aria-label={`${label} — open detail`}
      >
        {body}
      </Link>
    );
  }

  return <div className={shell}>{body}</div>;
}

function BookPressureBar({ book }: { book: BookPressure }) {
  const bid = book.bid_share_pct;
  if (bid == null || !Number.isFinite(bid)) {
    return (
      <div className="space-y-1.5">
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full w-1/2 bg-muted-foreground/25" />
        </div>
        <div className="flex justify-between font-mono text-[10px] text-muted-foreground">
          <span>Bid —</span>
          <span>Ask —</span>
        </div>
      </div>
    );
  }
  const pct = Math.max(0, Math.min(100, bid));
  return (
    <div className="space-y-1.5">
      <div
        className="relative h-2.5 w-full overflow-hidden rounded-full bg-rose-200/80 dark:bg-rose-950/50"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        aria-label={`Bid share ${pct.toFixed(0)} percent of sampled book`}
      >
        <div
          className="h-full bg-emerald-600/85 transition-[width] duration-500 ease-out motion-reduce:transition-none"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between font-mono text-[10px] tabular-nums text-muted-foreground">
        <span>Bid {pct.toFixed(0)}%</span>
        <span>Ask {(100 - pct).toFixed(0)}%</span>
      </div>
    </div>
  );
}

function bookDetail(book: BookPressure): string {
  if (book.sample_n <= 0) return "No public book sample yet";
  const imb =
    book.imbalance_pct == null
      ? "—"
      : `${book.imbalance_pct > 0 ? "+" : ""}${book.imbalance_pct.toFixed(1)}%`;
  return `${book.sample_n} symbols · imb ${imb} · public totals`;
}

/**
 * Overview tape pulse — Appetite · Foreign · Book (Tremor/HyperUI pattern-copy).
 * One composition; not a CSEPal Macro tab farm.
 */
export function TapePulseStrip({
  appetiteLatest,
  appetiteHistory,
  appetiteDelta1,
  foreign,
  foreignHistory,
  foreignDelta,
  book,
  className,
}: {
  appetiteLatest: AppetiteDay | null;
  appetiteHistory: AppetiteDay[];
  appetiteDelta1: number | null;
  foreign: ForeignDay | null;
  foreignHistory: ForeignDay[];
  foreignDelta: number | null;
  book: BookPressure;
  className?: string;
}) {
  const foreignNet = foreign?.foreign_net ?? null;
  const foreignTone: "up" | "down" | "flat" =
    foreignNet == null ? "flat" : foreignNet > 0 ? "up" : foreignNet < 0 ? "down" : "flat";
  const foreignDeltaTone: "up" | "down" | "flat" =
    foreignDelta == null
      ? "flat"
      : foreignDelta > 0
        ? "up"
        : foreignDelta < 0
          ? "down"
          : "flat";

  const bookValue =
    book.label === "bid_heavy"
      ? "Bid heavy"
      : book.label === "ask_heavy"
        ? "Ask heavy"
        : book.label === "balanced"
          ? "Balanced"
          : "—";

  const appetiteScores = appetiteHistory.slice(-60).map((d) => d.score);
  const foreignNets = foreignHistory.map((d) => d.foreign_net);

  return (
    <section
      className={cn(
        "rounded-xl border border-border/80 bg-gradient-to-b from-muted/35 to-muted/10 px-3 py-4 sm:px-5 sm:py-5",
        className,
      )}
      aria-labelledby="tape-pulse-heading"
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p
            id="tape-pulse-heading"
            className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground"
          >
            CSE tape pulse
          </p>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Session appetite, foreign flow, and public book pressure — not tips.{" "}
            <Link
              href="/help#tape-pulse"
              className="underline underline-offset-4 transition-colors hover:text-foreground"
            >
              How tape pulse works
            </Link>
            . Tap a card for detail.
          </p>
        </div>
        <Link
          href="/context"
          className="text-xs font-medium text-foreground underline-offset-4 hover:underline"
        >
          Context →
        </Link>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <Chip
          href="/appetite"
          label="Market Appetite"
          value={
            appetiteLatest ? String(Math.round(appetiteLatest.score)) : "—"
          }
          detail={
            appetiteLatest
              ? `${BAND_LABEL[appetiteLatest.band]} · ${appetiteLatest.trade_date} · n=${appetiteLatest.universe_n}`
              : "Run appetite-backfill"
          }
          delta={appetiteLatest ? fmtDelta(appetiteDelta1) : undefined}
          deltaTone={
            (appetiteDelta1 ?? 0) > 0
              ? "up"
              : (appetiteDelta1 ?? 0) < 0
                ? "down"
                : "flat"
          }
          status={
            appetiteLatest ? (
              <AppetiteBandBadge
                band={appetiteLatest.band}
                className="text-xs shadow-none"
              />
            ) : null
          }
          spark={
            appetiteLatest && appetiteScores.length >= 2 ? (
              <AreaSpark
                values={appetiteScores}
                labels={appetiteHistory.slice(-60).map((d) => d.trade_date)}
                tone="neutral"
                heightClass="h-14"
                ariaLabel="Appetite score spark, last 60 sessions"
              />
            ) : null
          }
        >
          {appetiteLatest ? (
            <AppetiteMeter
              score={appetiteLatest.score}
              band={appetiteLatest.band}
              size="sm"
            />
          ) : null}
        </Chip>

        <Chip
          href="/foreign"
          label="Foreign net"
          value={fmtLkr(foreignNet)}
          detail={
            foreign
              ? `${foreign.trade_date}${
                  foreign.foreign_share_pct != null
                    ? ` · ${foreign.foreign_share_pct.toFixed(1)}% of turnover`
                    : ""
                }`
              : "Accruing market_daily_summary"
          }
          delta={
            foreignDelta != null ? fmtLkr(foreignDelta) + " Δ" : undefined
          }
          deltaTone={foreignDeltaTone}
          status={
            <span
              className={cn(
                "inline-flex w-fit rounded-md px-2 py-0.5 text-xs font-medium",
                foreignTone === "up" &&
                  "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300",
                foreignTone === "down" &&
                  "bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-300",
                foreignTone === "flat" && "bg-muted text-muted-foreground",
              )}
            >
              {foreignNet == null
                ? "No session yet"
                : foreignNet > 0
                  ? "Net buying"
                  : foreignNet < 0
                    ? "Net selling"
                    : "Flat"}
            </span>
          }
          spark={
            foreignNets.filter((v) => v != null).length >= 2 ? (
              <AreaSpark
                values={foreignNets}
                labels={foreignHistory.map((d) => d.trade_date)}
                heightClass="h-14"
                ariaLabel="Foreign net spark"
              />
            ) : null
          }
        />

        <Chip
          href="/book"
          label="Book pressure"
          value={bookValue}
          detail={bookDetail(book)}
          spark={
            <p className="text-[10px] leading-snug text-muted-foreground">
              Public CSE bid/ask totals sample — not licensed L2 depth.
            </p>
          }
        >
          <BookPressureBar book={book} />
        </Chip>
      </div>

      {appetiteHistory.length > 0 ? (
        <div className="mt-4 border-t border-border/60 pt-3.5">
          <AppetiteTracker historyAsc={appetiteHistory} limit={60} />
        </div>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <NfaInline />
        <div className="flex flex-wrap gap-3 text-xs">
          <Link
            href="/appetite"
            className="font-medium underline-offset-4 hover:underline"
          >
            Appetite
          </Link>
          <Link
            href="/foreign"
            className="font-medium underline-offset-4 hover:underline"
          >
            Foreign
          </Link>
          <Link
            href="/book"
            className="font-medium underline-offset-4 hover:underline"
          >
            Book
          </Link>
          <Link
            href="/alerts"
            className="font-medium underline-offset-4 hover:underline"
          >
            Arm Telegram
          </Link>
        </div>
      </div>
    </section>
  );
}
