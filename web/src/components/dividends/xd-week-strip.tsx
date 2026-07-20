import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { UpcomingDividendEvent } from "@/lib/db/dividend-events";
import {
  formatDividendDate,
  shortDividendTitle,
} from "@/lib/dividends";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Relative XD countdown using Asia/Colombo calendar day. */
export function daysUntilLabel(date: string | null): string {
  if (!date) return "XD date unknown";
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) return date;
  const target = Date.UTC(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
  );
  // Colombo "today" via Intl parts (no date-fns dependency).
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Colombo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const y = Number(parts.find((p) => p.type === "year")?.value);
  const m = Number(parts.find((p) => p.type === "month")?.value);
  const d = Number(parts.find((p) => p.type === "day")?.value);
  if (!y || !m || !d) return formatDividendDate(date);
  const today = Date.UTC(y, m - 1, d);
  const days = Math.round((target - today) / 86_400_000);
  if (days < 0) return "Passed";
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return `${days} days`;
}

export function XdWeekStrip({
  items,
  className,
}: {
  items: UpcomingDividendEvent[];
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-xl border border-border/70 bg-card/60 p-4",
        className,
      )}
      aria-labelledby="xd-week-strip-heading"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2
            id="xd-week-strip-heading"
            className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
          >
            XD this week
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Watchlist dividends from stored CSE disclosures. Market stays open
            on XD day.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link
            href="/alerts?type=xd_soon"
            className="text-xs text-muted-foreground underline-offset-4 hover:underline"
          >
            Alert on XD
          </Link>
          <Link
            href="/dividends"
            className="text-xs text-muted-foreground underline-offset-4 hover:underline"
          >
            Calculator
          </Link>
        </div>
      </div>

      {items.length === 0 ? (
        <p className="mt-3 rounded-lg border border-dashed border-border/80 px-3 py-2 text-sm text-muted-foreground">
          No watched symbols go XD in the next 7 days.{" "}
          <Link
            href="/alerts?type=xd_soon"
            className="underline-offset-4 hover:underline"
          >
            Arm an XD alert
          </Link>{" "}
          or open the calculator.
        </p>
      ) : (
        <ul className="mt-3 grid gap-2 lg:grid-cols-2">
          {items.slice(0, 8).map((item) => (
            <li
              key={item.id}
              className="flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-lg border border-border/70 bg-background px-3 py-2"
            >
              <div className="min-w-0">
                <Link
                  href={`/symbols/${encodeURIComponent(item.symbol)}`}
                  className="font-mono text-sm font-semibold underline-offset-2 hover:underline"
                >
                  {item.symbol}
                </Link>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">
                  {shortDividendTitle(item.title, item.kind ?? "Dividend")}
                  {item.kind ? ` · ${item.kind}` : ""}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
                <Badge variant="outline" className="font-mono tabular-nums">
                  XD {formatDividendDate(item.d_xd)}
                </Badge>
                {item.d_pay ? (
                  <Badge
                    variant="outline"
                    className="font-mono tabular-nums text-muted-foreground"
                  >
                    Pay {formatDividendDate(item.d_pay)}
                  </Badge>
                ) : null}
                <span className="text-xs text-muted-foreground">
                  {daysUntilLabel(item.d_xd)}
                </span>
                {item.dps != null ? (
                  <span className="font-mono text-xs tabular-nums text-foreground">
                    {formatNumber(item.dps)} DPS
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
