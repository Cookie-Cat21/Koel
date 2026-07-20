import Link from "next/link";
import type { ReactNode } from "react";

import {
  AppetiteBandBadge,
  AppetiteMeter,
} from "@/components/appetite/appetite-meter";
import { AppetiteTracker } from "@/components/appetite/appetite-tracker";
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

function MiniSpark({
  values,
  upIsGood = true,
}: {
  values: Array<number | null>;
  upIsGood?: boolean;
}) {
  const series = values.filter((v): v is number => v != null && Number.isFinite(v));
  if (series.length < 2) return null;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const span = max !== min ? max - min : 1;
  const w = 120;
  const h = 36;
  const pad = 2;
  const pts = series
    .map((v, i) => {
      const x = pad + (i / (series.length - 1)) * (w - pad * 2);
      const y = pad + (1 - (v - min) / span) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const up = series[series.length - 1]! >= series[0]!;
  const good = upIsGood ? up : !up;
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-9 w-full"
      role="img"
      aria-hidden
    >
      <polyline
        fill="none"
        stroke={good ? "oklch(0.45 0.08 185)" : "oklch(0.5 0.1 25)"}
        strokeWidth="1.75"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={pts}
      />
    </svg>
  );
}

function Chip({
  label,
  value,
  detail,
  delta,
  deltaTone,
  children,
  className,
}: {
  label: string;
  value: string;
  detail: string;
  delta?: string;
  deltaTone?: "up" | "down" | "flat";
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-1 flex-col gap-2 rounded-md border border-border/70 bg-background/60 px-3 py-3",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          {label}
        </p>
        {delta ? (
          <span
            className={cn(
              "inline-flex items-center rounded-sm px-1.5 py-0.5 font-mono text-[10px] tabular-nums",
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
      </div>
      <p className="font-mono text-2xl font-semibold tabular-nums tracking-tight">
        {value}
      </p>
      <p className="font-mono text-[11px] tabular-nums text-muted-foreground">
        {detail}
      </p>
      {children}
    </div>
  );
}

function BookPressureBar({ book }: { book: BookPressure }) {
  const bid = book.bid_share_pct;
  if (bid == null || !Number.isFinite(bid)) {
    return (
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full w-1/2 bg-muted-foreground/30" />
      </div>
    );
  }
  const pct = Math.max(0, Math.min(100, bid));
  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full bg-rose-200/70 dark:bg-rose-950/40"
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      aria-label={`Bid share ${pct.toFixed(0)} percent of sampled book`}
    >
      <div
        className="h-full rounded-full bg-emerald-600/80 transition-[width] duration-500"
        style={{ width: `${pct}%` }}
      />
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

  return (
    <section
      className={cn(
        "rounded-lg border border-border/80 bg-muted/15 px-3 py-4 sm:px-4",
        className,
      )}
      aria-labelledby="tape-pulse-heading"
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p
            id="tape-pulse-heading"
            className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground"
          >
            CSE tape pulse
          </p>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Session appetite, foreign flow, and public book pressure — not tips.
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
        >
          {appetiteLatest ? (
            <>
              <div className="flex items-center gap-2">
                <AppetiteBandBadge band={appetiteLatest.band} />
              </div>
              <AppetiteMeter
                score={appetiteLatest.score}
                band={appetiteLatest.band}
                size="sm"
                className="mt-1"
              />
              <MiniSpark values={appetiteHistory.slice(-60).map((d) => d.score)} />
            </>
          ) : null}
        </Chip>

        <Chip
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
        >
          <span
            className={cn(
              "inline-flex w-fit rounded-sm px-1.5 py-0.5 text-[10px] font-medium",
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
          <MiniSpark
            values={foreignHistory.map((d) => d.foreign_net)}
            upIsGood
          />
        </Chip>

        <Chip
          label="Book pressure"
          value={bookValue}
          detail={bookDetail(book)}
        >
          <BookPressureBar book={book} />
          <p className="text-[10px] text-muted-foreground">
            Public CSE bid/ask totals sample — not licensed L2 depth.
          </p>
        </Chip>
      </div>

      {appetiteHistory.length > 0 ? (
        <div className="mt-4 border-t border-border/60 pt-3">
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
            Appetite history
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
