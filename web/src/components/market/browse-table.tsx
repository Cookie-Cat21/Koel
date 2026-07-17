"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";

import { ChangeBadge } from "@/components/kit/change-badge";
import { formatNumber, formatTs } from "@/lib/format";

export type BrowseRow = {
  symbol: string;
  name: string | null;
  sector: string | null;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  ts: string | null;
};

/**
 * Dense CSE browse table — FinancialTable DNA without US-index columns.
 * Postgres snapshot rows only. Research / NFA.
 */
export function BrowseTable({ items }: { items: BrowseRow[] }) {
  const reduceMotion = useReducedMotion();

  return (
    <>
      <div className="mt-8 hidden overflow-x-auto rounded-2xl border border-border/50 md:block">
        <div className="min-w-[900px]">
          <div
            className="grid gap-x-2 border-b border-border/20 bg-muted/15 px-6 py-3 text-left text-xs font-medium tracking-wide text-muted-foreground/80 uppercase"
            style={{
              gridTemplateColumns:
                "minmax(140px,1.2fr) minmax(160px,1.4fr) minmax(120px,1fr) minmax(90px,0.8fr) minmax(90px,0.8fr) minmax(100px,0.9fr) minmax(110px,0.9fr)",
            }}
          >
            <div>Symbol</div>
            <div>Name</div>
            <div>Sector</div>
            <div className="text-right">Price</div>
            <div className="text-right">Change</div>
            <div className="text-right">Daily %</div>
            <div className="text-right">Updated</div>
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
            {items.map((item) => (
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
                <Link
                  href={`/symbols/${encodeURIComponent(item.symbol)}`}
                  className="grid gap-x-2 border-b border-border/20 px-6 py-3 text-sm transition-colors hover:bg-muted/35 focus-visible:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                  style={{
                    gridTemplateColumns:
                      "minmax(140px,1.2fr) minmax(160px,1.4fr) minmax(120px,1fr) minmax(90px,0.8fr) minmax(90px,0.8fr) minmax(100px,0.9fr) minmax(110px,0.9fr)",
                  }}
                >
                  <div className="font-mono font-medium text-foreground">
                    {item.symbol}
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
                </Link>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>

      {/* Mobile list */}
      <ul
        className="mt-8 divide-y divide-border/60 md:hidden"
        aria-label="Market symbols"
      >
        {items.map((item) => (
          <li key={item.symbol}>
            <Link
              href={`/symbols/${encodeURIComponent(item.symbol)}`}
              className="flex flex-wrap items-center justify-between gap-3 py-3 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              <div className="min-w-0">
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
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1 text-sm">
                <p className="font-mono tabular-nums">
                  {formatNumber(item.price)}
                </p>
                <ChangeBadge changePct={item.change_pct} />
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
