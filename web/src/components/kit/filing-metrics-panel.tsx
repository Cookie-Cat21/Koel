import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import Link from "next/link";

import { ExpandableBrief } from "@/components/kit/expandable-brief";
import { Badge } from "@/components/ui/badge";
import {
  formatCompactNumber,
  formatNumber,
  formatPct,
  formatTs,
} from "@/lib/format";
import { cn } from "@/lib/utils";

export type FilingMetricRow = {
  kind: string | null;
  entity: string | null;
  currency: string | null;
  fiscal_period_end: string | null;
  eps_basic: number | null;
  revenue: number | null;
  profit: number | null;
  extract_ok: boolean;
};

export type FilingMetricComparison = {
  match_quality: "exact_yoy" | "approx_yoy" | null;
  eps_delta_pct: number | null;
  revenue_delta_pct: number | null;
  profit_delta_pct: number | null;
};

export type LatestBrief = {
  title: string;
  text: string;
};

function yoyMatchLabel(quality: "exact_yoy" | "approx_yoy"): string {
  return quality === "exact_yoy"
    ? "Exact prior-year period"
    : "Approximate prior-year match";
}

export function FilingMetricsPanel({
  metrics,
  comparison,
  latestBrief,
  loadFailed = false,
  emptyMetricsHint,
  emptyBriefHint,
  className,
}: {
  metrics: FilingMetricRow | null;
  comparison: FilingMetricComparison | null;
  latestBrief: LatestBrief | null;
  /** True when metrics API failed — distinct from empty extract. */
  loadFailed?: boolean;
  /** Optional override when quality signals explain the empty metrics state. */
  emptyMetricsHint?: string | null;
  /** Optional override when quality signals explain the empty brief state. */
  emptyBriefHint?: string | null;
  className?: string;
}) {
  const comparable =
    comparison?.match_quality === "exact_yoy" ||
    comparison?.match_quality === "approx_yoy";

  return (
    <section
      className={cn("mt-8 border-t border-border/60 pt-6", className)}
      aria-labelledby="filing-metrics-heading"
    >
      <div className="flex flex-col gap-6 lg:grid lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2
              id="filing-metrics-heading"
              className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
            >
              Filing metrics
            </h2>
            <Link
              href="/help#filing-metrics"
              className="text-xs text-muted-foreground underline underline-offset-4 transition-colors hover:text-foreground"
            >
              How metrics work
            </Link>
          </div>
          {loadFailed ? (
            <div
              className="mt-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4"
              role="alert"
            >
              <p className="text-sm text-destructive">
                Couldn’t load filing metrics right now. Retry in a moment — this
                is not an empty extract.
              </p>
            </div>
          ) : metrics ? (
            <div className="mt-3 rounded-lg border border-border/70 p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                {metrics.kind ? <span>{metrics.kind}</span> : null}
                {metrics.entity ? <span>· {metrics.entity}</span> : null}
                {metrics.currency ? <span>· {metrics.currency}</span> : null}
                {metrics.fiscal_period_end ? (
                  <span>
                    · period ended {formatMetricDate(metrics.fiscal_period_end)}
                  </span>
                ) : null}
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <MetricValue
                  label="Basic EPS"
                  value={formatNumber(metrics.eps_basic, 4)}
                  fullValue={formatNumber(metrics.eps_basic, 4)}
                  deltaPct={comparable ? comparison?.eps_delta_pct : null}
                />
                <MetricValue
                  label="Revenue"
                  value={formatCompactNumber(metrics.revenue)}
                  fullValue={formatNumber(metrics.revenue, 0)}
                  deltaPct={comparable ? comparison?.revenue_delta_pct : null}
                />
                <MetricValue
                  label="Profit"
                  value={formatCompactNumber(metrics.profit)}
                  fullValue={formatNumber(metrics.profit, 0)}
                  deltaPct={comparable ? comparison?.profit_delta_pct : null}
                />
              </div>
              {comparable && comparison?.match_quality ? (
                <p className="mt-3 text-xs text-muted-foreground">
                  YoY comparison: {yoyMatchLabel(comparison.match_quality)}.
                  Extracted numbers need filing verification.
                </p>
              ) : (
                <p className="mt-3 text-xs text-muted-foreground">
                  No exact or approximate YoY comparison for this filing yet.
                </p>
              )}
            </div>
          ) : (
            <div className="mt-3 rounded-lg border border-dashed border-border/70 p-4">
              <p className="text-sm text-muted-foreground">
                {emptyMetricsHint?.trim()
                  ? emptyMetricsHint
                  : "No filing metrics extracted yet. Numbers appear after CSE financial-statement PDFs are ingested and parsed for this symbol. Extracted figures need filing verification."}
              </p>
            </div>
          )}
        </div>

        <div>
          <h3 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
            Latest brief
          </h3>
          {latestBrief ? (
            <ExpandableBrief
              className="mt-3"
              title={latestBrief.title}
              text={latestBrief.text}
            />
          ) : (
            <div className="mt-3 rounded-lg border border-dashed border-border/70 p-4">
              <p className="text-sm text-muted-foreground">
                {emptyBriefHint?.trim()
                  ? emptyBriefHint
                  : "No ready AI brief for this symbol yet. Briefs appear after a financial filing PDF is summarized (queue may lag on free-tier AI limits). Not financial advice."}
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function formatMetricDate(value: string | null): string {
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }
  return formatTs(value);
}

function MetricValue({
  label,
  value,
  fullValue,
  deltaPct,
}: {
  label: string;
  value: string;
  /** Exact figure for title / screen readers when value is compact. */
  fullValue?: string;
  deltaPct: number | null | undefined;
}) {
  const title =
    fullValue && fullValue !== "—" && fullValue !== value ? fullValue : undefined;
  return (
    <div className="min-w-0 rounded-md bg-muted/30 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className="mt-1 break-words font-mono text-lg font-medium leading-snug tabular-nums"
        title={title}
      >
        <span className="sr-only">{title ? `${fullValue}. Displayed as ` : null}</span>
        {value}
      </p>
      {title ? (
        <p className="mt-0.5 font-mono text-[11px] leading-snug text-muted-foreground tabular-nums">
          {fullValue}
        </p>
      ) : null}
      <div className="mt-2">
        <YoyBadge value={deltaPct} />
      </div>
    </div>
  );
}

function YoyBadge({ value }: { value: number | null | undefined }) {
  if (value == null || !Number.isFinite(value)) {
    return (
      <Badge
        variant="outline"
        className="border-border bg-muted/50 font-mono text-muted-foreground"
      >
        <Minus className="size-3" aria-hidden />
        YoY —
      </Badge>
    );
  }

  const up = value > 0;
  const down = value < 0;
  const Icon = up ? ArrowUp : down ? ArrowDown : Minus;

  return (
    <Badge
      variant="outline"
      className={cn(
        "font-mono tabular-nums",
        up &&
          "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        down &&
          "border-destructive/30 bg-destructive/10 text-destructive",
        !up && !down && "border-border bg-muted/50 text-muted-foreground",
      )}
    >
      <Icon className="size-3" aria-hidden />
      YoY {formatPct(value)}
    </Badge>
  );
}
