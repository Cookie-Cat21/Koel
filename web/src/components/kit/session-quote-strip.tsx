import { HelpLink } from "@/components/help-link";
import { formatCompactNumber, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export type SessionQuoteFields = {
  previous_close: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  trade_count: number | null;
  turnover: number | null;
  market_cap: number | null;
  /** Fallback prev from last − change when snapshot previous_close missing. */
  derived_prev_close: number | null;
};

type Cell = { label: string; value: string; hint?: string };

/**
 * Dense CSE-style session quote board (HyperUI stats-grid pattern).
 * Research labels from stored snapshots — not a live trading terminal.
 */
export function SessionQuoteStrip({
  quote,
  className,
}: {
  quote: SessionQuoteFields;
  className?: string;
}) {
  const prev =
    quote.previous_close ?? quote.derived_prev_close ?? null;
  const dayRange =
    quote.high != null && quote.low != null
      ? `${formatNumber(quote.high)} – ${formatNumber(quote.low)}`
      : null;

  const cells: Cell[] = [
    {
      label: "Prev close",
      value: prev == null ? "—" : formatNumber(prev),
    },
    {
      label: "Open",
      value: quote.open == null ? "—" : formatNumber(quote.open),
    },
    {
      label: "Day range",
      value: dayRange ?? "—",
      hint: "Session high – low from last stored print",
    },
    {
      label: "Volume",
      value:
        quote.volume == null
          ? "—"
          : formatNumber(Math.round(quote.volume), 0),
    },
    {
      label: "Trades",
      value:
        quote.trade_count == null
          ? "—"
          : formatNumber(Math.round(quote.trade_count), 0),
    },
    {
      label: "Turnover",
      value:
        quote.turnover == null
          ? "—"
          : formatCompactNumber(quote.turnover),
    },
  ];
  if (quote.market_cap != null) {
    cells.push({
      label: "Market cap",
      value: formatCompactNumber(quote.market_cap),
    });
  }

  const hasAny = cells.some((c) => c.value !== "—");
  if (!hasAny) return null;

  return (
    <div
      className={cn("border-t border-border/60", className)}
      aria-label="Session quote"
    >
      <div className="flex flex-wrap items-center gap-2 px-5 pt-3 sm:px-6">
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Session
        </span>
        <HelpLink
          topic="symbol-quote"
          variant="text"
          className="text-[11px] text-muted-foreground"
        >
          Quote help
        </HelpLink>
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-px bg-border/40 sm:grid-cols-3 lg:grid-cols-4">
        {cells.map((cell) => (
          <div
            key={cell.label}
            className="min-w-0 bg-background px-4 py-3 transition-colors focus-within:bg-muted/30"
            title={cell.hint}
          >
            <dt className="text-xs text-muted-foreground">{cell.label}</dt>
            <dd className="mt-0.5 truncate font-mono text-base font-medium tabular-nums sm:text-lg">
              {cell.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
