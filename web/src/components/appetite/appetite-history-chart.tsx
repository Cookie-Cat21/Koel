"use client";

import { useMemo, useState } from "react";

import {
  BAND_ZONE_COLOR,
  bandForScore,
  type AppetiteDay,
} from "@/lib/api/appetite";
import { cn } from "@/lib/utils";

type RangeKey = "3M" | "1Y" | "5Y" | "MAX";

/** Calendar-day windows. 5Y/MAX prefer hybrid research when loaded. */
const RANGE_CALENDAR_DAYS: Record<Exclude<RangeKey, "MAX">, number> = {
  "3M": 92,
  "1Y": 365,
  "5Y": 365 * 5,
};

/** Draw at most this many points — long hybrid ranges get aggregated. */
const MAX_DRAW_POINTS = 220;

type AggregateMode = "none" | "week" | "month";

function parseTradeDateMs(iso: string): number {
  const t = Date.parse(`${iso}T12:00:00Z`);
  return Number.isFinite(t) ? t : Number.NaN;
}

function sliceByCalendarDays(
  historyAsc: AppetiteDay[],
  calendarDays: number,
): AppetiteDay[] {
  if (historyAsc.length === 0) return historyAsc;
  const last = historyAsc[historyAsc.length - 1]!;
  const endMs = parseTradeDateMs(last.trade_date);
  if (!Number.isFinite(endMs)) {
    return historyAsc.slice(-(calendarDays <= 100 ? 63 : 252));
  }
  const startMs = endMs - calendarDays * 86_400_000;
  const sliced = historyAsc.filter((d) => {
    const ms = parseTradeDateMs(d.trade_date);
    return Number.isFinite(ms) && ms >= startMs;
  });
  return sliced.length >= 2 ? sliced : historyAsc.slice(-2);
}

/**
 * Hybrid research series often lags the live CSE path. Append CSE days after
 * the hybrid tip so MAX reaches the latest session without inventing scores.
 */
export function stitchHybridWithCse(
  hybridAsc: AppetiteDay[],
  cseAsc: AppetiteDay[],
): AppetiteDay[] {
  if (hybridAsc.length < 2) return cseAsc;
  if (cseAsc.length === 0) return hybridAsc;
  const tip = hybridAsc[hybridAsc.length - 1]!.trade_date;
  const tipMs = parseTradeDateMs(tip);
  if (!Number.isFinite(tipMs)) return hybridAsc;
  const tail = cseAsc.filter((d) => {
    const ms = parseTradeDateMs(d.trade_date);
    return Number.isFinite(ms) && ms > tipMs;
  });
  return tail.length === 0 ? hybridAsc : [...hybridAsc, ...tail];
}

/** UTC ISO week key — Monday-based YYYY-Www. */
export function weekBucketKey(iso: string): string | null {
  const ms = parseTradeDateMs(iso);
  if (!Number.isFinite(ms)) return null;
  const d = new Date(ms);
  // ISO week: Thursday determines year; Monday is week start.
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

export function monthBucketKey(iso: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  return iso.slice(0, 7);
}

/**
 * Collapse dense daily appetite into week/month averages so long charts stay
 * readable. Keeps the last session's date+score as the final point so the tip
 * matches the live headline.
 */
export function aggregateAppetiteSeries(
  days: AppetiteDay[],
  mode: AggregateMode,
): AppetiteDay[] {
  if (mode === "none" || days.length < 3) return days;
  const keyFn = mode === "week" ? weekBucketKey : monthBucketKey;
  const buckets = new Map<string, AppetiteDay[]>();
  const order: string[] = [];
  for (const d of days) {
    const key = keyFn(d.trade_date);
    if (!key) continue;
    if (!buckets.has(key)) {
      buckets.set(key, []);
      order.push(key);
    }
    buckets.get(key)!.push(d);
  }
  if (order.length < 2) return days;

  const out: AppetiteDay[] = [];
  for (const key of order) {
    const group = buckets.get(key)!;
    const last = group[group.length - 1]!;
    const mean =
      group.reduce((sum, g) => sum + g.score, 0) / Math.max(1, group.length);
    const score = Math.max(0, Math.min(100, mean));
    out.push({
      ...last,
      score,
      band: bandForScore(score),
    });
  }

  // Tip fidelity — last plotted point = latest raw session score/date.
  const tip = days[days.length - 1]!;
  if (out.length > 0) {
    out[out.length - 1] = tip;
  }
  return out;
}

/** Pick aggregation so drawn points stay near MAX_DRAW_POINTS. */
export function chooseAggregateMode(pointCount: number): AggregateMode {
  if (pointCount <= MAX_DRAW_POINTS) return "none";
  // ~5 trading days/week → weekly if that lands under the cap.
  if (pointCount / 5 <= MAX_DRAW_POINTS) return "week";
  return "month";
}

function formatAxisDate(iso: string): string {
  const ms = parseTradeDateMs(iso);
  if (!Number.isFinite(ms)) return iso;
  const d = new Date(ms);
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${months[d.getUTCMonth()]} ${String(d.getUTCFullYear()).slice(2)}`;
}

function formatAxisDay(iso: string): string {
  const ms = parseTradeDateMs(iso);
  if (!Number.isFinite(ms)) return iso;
  const d = new Date(ms);
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${months[d.getUTCMonth()]} ${d.getUTCDate()}`;
}

function tickIndexes(n: number, target = 5): number[] {
  if (n <= 1) return [0];
  if (n <= target) return Array.from({ length: n }, (_, i) => i);
  const out: number[] = [];
  for (let i = 0; i < target; i++) {
    out.push(Math.round((i * (n - 1)) / (target - 1)));
  }
  return [...new Set(out)];
}

/**
 * Appetite history chart.
 * 3M / 1Y = CSE-truth daily path.
 * 5Y / MAX = Yahoo+CSE hybrid when loaded (falls back to CSE), drawn as
 * weekly/monthly averages when the raw series is too dense to read.
 */
export function AppetiteHistoryChart({
  historyAsc,
  hybridHistoryAsc = [],
  className,
}: {
  historyAsc: AppetiteDay[];
  /** Long research series (source=hybrid_research). Used for 5Y / MAX. */
  hybridHistoryAsc?: AppetiteDay[];
  className?: string;
}) {
  const [range, setRange] = useState<RangeKey>("1Y");
  const maxSeries = useMemo(
    () => stitchHybridWithCse(hybridHistoryAsc, historyAsc),
    [hybridHistoryAsc, historyAsc],
  );
  const hasHybrid = hybridHistoryAsc.length >= 2;

  const rawSeries = useMemo(() => {
    if (range === "MAX") {
      return hasHybrid ? maxSeries : historyAsc;
    }
    if (range === "5Y") {
      const base = hasHybrid ? maxSeries : historyAsc;
      return sliceByCalendarDays(base, RANGE_CALENDAR_DAYS["5Y"]);
    }
    return sliceByCalendarDays(historyAsc, RANGE_CALENDAR_DAYS[range]);
  }, [historyAsc, maxSeries, hasHybrid, range]);

  const aggregateMode = useMemo(
    () => chooseAggregateMode(rawSeries.length),
    [rawSeries.length],
  );

  const series = useMemo(
    () => aggregateAppetiteSeries(rawSeries, aggregateMode),
    [rawSeries, aggregateMode],
  );

  const usingHybridLong =
    (range === "MAX" || range === "5Y") && hasHybrid;

  if (series.length < 2) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Need at least two sessions of appetite history.
      </p>
    );
  }

  const w = 720;
  const h = 248;
  const padL = 36;
  const padR = 16;
  const padT = 16;
  const padB = 44;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;

  const coords = series.map((d, i) => {
    const x = padL + (i / (series.length - 1)) * plotW;
    const y = padT + (1 - d.score / 100) * plotH;
    return { x, y, d };
  });

  const line = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ");
  const area = `${padL},${padT + plotH} ${line} ${padL + plotW},${padT + plotH}`;

  const zoneBands: { y0: number; y1: number; color: string }[] = [
    { y0: 0, y1: 20, color: BAND_ZONE_COLOR.extreme_caution },
    { y0: 20, y1: 40, color: BAND_ZONE_COLOR.caution },
    { y0: 40, y1: 60, color: BAND_ZONE_COLOR.neutral },
    { y0: 60, y1: 80, color: BAND_ZONE_COLOR.appetite },
    { y0: 80, y1: 100, color: BAND_ZONE_COLOR.strong_appetite },
  ];

  const first = series[0]!;
  const last = series[series.length - 1]!;
  const xTicks = tickIndexes(
    series.length,
    usingHybridLong || range === "5Y" ? 6 : series.length <= 80 ? 4 : 6,
  );
  const shortWindow = range === "3M";
  const aggLabel =
    aggregateMode === "month"
      ? "monthly avg"
      : aggregateMode === "week"
        ? "weekly avg"
        : null;

  return (
    <div className={cn("w-full", className)}>
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        {(["3M", "1Y", "5Y", "MAX"] as const).map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setRange(k)}
            aria-pressed={range === k}
            className={cn(
              "min-h-9 rounded-md border px-2.5 py-1 font-mono text-[11px] tabular-nums",
              range === k
                ? "border-foreground/30 bg-foreground text-background"
                : "border-border bg-muted/30 text-muted-foreground hover:bg-muted/60",
            )}
          >
            {k}
          </button>
        ))}
        <span className="ml-auto font-mono text-[11px] tabular-nums text-muted-foreground">
          {first.trade_date} → {last.trade_date}
          {aggLabel ? ` · ${aggLabel}` : ""} · {rawSeries.length.toLocaleString()}{" "}
          sessions · min{" "}
          {Math.round(Math.min(...series.map((d) => d.score)))} / max{" "}
          {Math.round(Math.max(...series.map((d) => d.score)))}
        </span>
      </div>
      {usingHybridLong ? (
        <p
          className="mb-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-1.5 text-xs text-foreground"
          role="status"
        >
          Research reconstruction (Yahoo + CSE) — not CSE official. 3M / 1Y stay
          on the CSE-truth path.
          {aggLabel
            ? ` ${range} draws ${aggLabel} so the long path stays readable.`
            : null}{" "}
          Recent sessions after the hybrid tip use CSE.
        </p>
      ) : null}
      {(range === "MAX" || range === "5Y") && !hasHybrid ? (
        <p className="mb-2 text-xs text-muted-foreground" role="status">
          {range} is meant to be Yahoo+CSE hybrid research history. Hybrid
          appetite scores are not loaded yet — showing CSE path until
          ``appetite-backfill --hybrid`` finishes.
        </p>
      ) : null}
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Market Appetite from ${first.trade_date} to ${last.trade_date}, latest ${Math.round(last.score)}${usingHybridLong ? ", Yahoo+CSE research" : ""}${aggLabel ? `, ${aggLabel}` : ""}`}
      >
        {zoneBands.map((z) => {
          const yTop = padT + (1 - z.y1 / 100) * plotH;
          const yBot = padT + (1 - z.y0 / 100) * plotH;
          return (
            <rect
              key={`${z.y0}-${z.y1}`}
              x={padL}
              y={yTop}
              width={plotW}
              height={Math.max(0, yBot - yTop)}
              fill={z.color}
              opacity={0.22}
            />
          );
        })}
        {[0, 20, 40, 60, 80, 100].map((v) => {
          const y = padT + (1 - v / 100) * plotH;
          return (
            <g key={v}>
              <line
                x1={padL}
                x2={padL + plotW}
                y1={y}
                y2={y}
                stroke="currentColor"
                strokeOpacity={v % 40 === 0 ? 0.14 : 0.07}
                strokeDasharray={v % 40 === 0 ? undefined : "3 4"}
              />
              <text
                x={padL - 6}
                y={y + 3}
                textAnchor="end"
                className="fill-muted-foreground"
                fontSize={10}
                fontFamily="ui-monospace, monospace"
              >
                {v}
              </text>
            </g>
          );
        })}
        <line
          x1={padL}
          x2={padL + plotW}
          y1={padT + plotH}
          y2={padT + plotH}
          stroke="currentColor"
          strokeOpacity={0.22}
        />
        {xTicks.map((idx) => {
          const c = coords[idx]!;
          const label = shortWindow
            ? formatAxisDay(c.d.trade_date)
            : formatAxisDate(c.d.trade_date);
          return (
            <g key={`x-${idx}-${c.d.trade_date}`}>
              <line
                x1={c.x}
                x2={c.x}
                y1={padT + plotH}
                y2={padT + plotH + 5}
                stroke="currentColor"
                strokeOpacity={0.28}
              />
              <text
                x={c.x}
                y={padT + plotH + 18}
                textAnchor="middle"
                className="fill-muted-foreground"
                fontSize={10}
                fontFamily="ui-monospace, monospace"
              >
                {label}
              </text>
            </g>
          );
        })}
        <polygon
          points={area}
          fill="currentColor"
          className="text-foreground"
          opacity={0.08}
        />
        <polyline
          points={line}
          fill="none"
          stroke="currentColor"
          className="text-foreground"
          strokeWidth={1.75}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <circle
          cx={coords[coords.length - 1]!.x}
          cy={coords[coords.length - 1]!.y}
          r={3.5}
          className="fill-foreground"
        />
      </svg>
    </div>
  );
}
