"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";

import { ChangeBadge } from "@/components/kit/change-badge";
import { formatNumber, formatTs } from "@/lib/format";
import { cn } from "@/lib/utils";

export type BrowseRow = {
  symbol: string;
  name: string | null;
  sector: string | null;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  ts: string | null;
};

const GRID_COLS =
  "minmax(140px,1.2fr) minmax(160px,1.4fr) minmax(120px,1fr) minmax(90px,0.8fr) minmax(90px,0.8fr) minmax(100px,0.9fr) minmax(110px,0.9fr) minmax(88px,0.7fr)";

/**
 * Dense CSE browse table — FinancialTable DNA without US-index columns.
 * Postgres snapshot rows only. Research / NFA.
 */
export function BrowseTable({
  items,
  className,
}: {
  items: BrowseRow[];
  className?: string;
}) {
  const reduceMotion = useReducedMotion();

  return (
    <>
      <div
        className={cn(
          "mt-4 hidden overflow-x-auto rounded-2xl border border-border/50 md:block",
          className,
        )}
      >
        <div className="min-w-[980px]">
          <div
            className="grid gap-x-2 border-b border-border/20 bg-muted/15 px-6 py-3 text-left text-xs font-medium tracking-wide text-muted-foreground/80 uppercase"
            style={{ gridTemplateColumns: GRID_COLS }}
          >
            <div>Symbol</div>
            <div>Name</div>
            <div>Sector</div>
            <div className="text-right">Price</div>
            <div className="text-right">Change</div>
            <div className="text-right">Daily %</div>
            <div className="text-right">Updated</div>
            <div className="text-right">Actions</div>
          </div>

          <motion.div
            initial={reduceMotion ? false : "hidden"}
            animate="visible"
            variants={{
              visible: {
                transition: {
                  staggerChildren: reduceMotion ? 0 : 0.02,
                  delayChildren: reduceMotion ? 0 : 0.05,
                },
              },
            }}
          >
            {items.map((item) => {
              const symbolHref = `/symbols/${encodeURIComponent(item.symbol)}`;
              const alertHref = `/alerts?symbol=${encodeURIComponent(item.symbol)}`;
              return (
                <motion.div
                  key={item.symbol}
                  variants={{
                    hidden: { opacity: 0, y: 8 },
                    visible: {
                      opacity: 1,
                      y: 0,
                      transition: {
                        type: "spring",
                        stiffness: 400,
                        damping: 28,
                      },
                    },
                  }}
                >
                  <div
                    className="grid gap-x-2 border-b border-border/20 px-6 py-3 text-sm transition-colors hover:bg-muted/35"
                    style={{ gridTemplateColumns: GRID_COLS }}
                  >
                    <div>
                      <Link
                        href={symbolHref}
                        className="font-mono font-medium text-foreground underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                      >
                        {item.symbol}
                      </Link>
                    </div>
                    <div
                      className="truncate text-muted-foreground"
                      title={item.name ?? undefined}
                    >
                      {item.name ?? "—"}
                    </div>
                    <div
                      className="truncate text-muted-foreground"
                      title={item.sector ?? undefined}
                    >
                      {item.sector ?? "—"}
                    </div>
                    <div className="text-right font-mono tabular-nums">
                      {formatNumber(item.price)}
                    </div>
                    <div
                      className={`text-right font-mono tabular-nums ${
                        item.change == null
                          ? "text-muted-foreground"
                          : item.change > 0
                            ? "text-emerald-600 dark:text-emerald-400"
                            : item.change < 0
                              ? "text-rose-600 dark:text-rose-400"
                              : "text-muted-foreground"
                      }`}
                    >
                      {item.change == null
                        ? "—"
                        : `${item.change > 0 ? "+" : ""}${formatNumber(item.change)}`}
                    </div>
                    <div className="flex justify-end">
                      <ChangeBadge changePct={item.change_pct} />
                    </div>
                    <div className="text-right text-xs text-muted-foreground">
                      {formatTs(item.ts)}
                    </div>
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        href={alertHref}
                        className="rounded-sm text-xs font-medium text-foreground underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                      >
                        Alert
                      </Link>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>
        </div>
      </div>

      {/* Mobile list */}
      <ul
        className="mt-4 divide-y divide-border/60 md:hidden"
        aria-label="Market symbols"
      >
        {items.map((item) => {
          const symbolHref = `/symbols/${encodeURIComponent(item.symbol)}`;
          const alertHref = `/alerts?symbol=${encodeURIComponent(item.symbol)}`;
          return (
            <li key={item.symbol} className="py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Link
                  href={symbolHref}
                  className="min-w-0 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  <p className="font-mono text-sm font-medium">{item.symbol}</p>
                  {item.name ? (
                    <p className="truncate text-sm text-muted-foreground">
                      {item.name}
                    </p>
                  ) : null}
                  {item.sector ? (
                    <p className="truncate text-xs text-muted-foreground">
                      {item.sector}
                    </p>
                  ) : null}
                </Link>
                <div className="flex shrink-0 flex-col items-end gap-1 text-sm">
                  <p className="font-mono tabular-nums">
                    {formatNumber(item.price)}
                  </p>
                  <ChangeBadge changePct={item.change_pct} />
                </div>
              </div>
              <div className="mt-2 flex min-h-11 items-center gap-4">
                <Link
                  href={alertHref}
                  className="inline-flex min-h-11 items-center text-sm font-medium text-foreground underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  Alert
                </Link>
                <Link
                  href={symbolHref}
                  className="inline-flex min-h-11 items-center text-sm text-muted-foreground underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  Open
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
    </>
  );
}
