"use client";

import { Maximize2, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

import { CandlestickChart } from "@/components/charts/candlestick-chart";
import { SparklineWithForecast } from "@/components/sparkline-with-forecast";
import { Button } from "@/components/ui/button";
import {
  type ChartRangeKey,
  type DailyBarPoint,
  sessionsForRange,
  ticksToIntradayBars,
} from "@/lib/api/daily-bars";
import { isSafeClientApiPath } from "@/lib/api/client-fetch";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { finiteSparklinePoints } from "@/lib/sparkline";
import { formatCompactNumber, formatNumber, formatPct } from "@/lib/format";

type Point = { ts: string | null; price: number | null | undefined };

const RANGES: ChartRangeKey[] = ["1D", "1M", "3M", "6M", "1Y"];
const REALTIME_MS = 20_000;

/**
 * Compact sparkline + corner expand → large chart dialog.
 * All ranges use candlesticks; 1D builds OHLC from realtime ticks.
 */
export function ExpandablePriceChart({
  symbol,
  points,
  forecastPoints,
  confidenceBand,
  gate,
  confidence,
  className,
  initialOpen = false,
  initialBars = null,
  initialRange = "1D",
}: {
  symbol: string;
  points: Point[];
  forecastPoints?: Point[];
  confidenceBand?: string | null;
  gate?: string | null;
  confidence?: number | null;
  className?: string;
  initialOpen?: boolean;
  initialBars?: DailyBarPoint[] | null;
  initialRange?: ChartRangeKey;
}) {
  const titleId = useId();
  const forecastToggleId = useId();
  const [open, setOpen] = useState(Boolean(initialOpen));
  const [range, setRange] = useState<ChartRangeKey>(initialRange);
  const [bars, setBars] = useState<DailyBarPoint[] | null>(
    initialBars && initialBars.length > 0 ? initialBars : null,
  );
  // Realtime ticks fetched client-side; falls back to SSR `points` until the
  // first refresh lands (derived, so prop updates never need a reset effect).
  const [fetchedTicks, setFetchedTicks] = useState<Point[] | null>(null);
  const tickPoints = fetchedTicks ?? points;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForecast, setShowForecast] = useState(
    () =>
      confidenceBand === "high" ||
      gate === "gated_p90" ||
      gate === "hpe_p90" ||
      gate === "gated_c55" ||
      gate === "gated" ||
      gate === "gated_ltr",
  );
  const [lastRefresh, setLastRefresh] = useState<string | null>(null);

  const forecastPrices = useMemo(
    () =>
      (forecastPoints ?? [])
        .map((p) => toFiniteNumber(p.price))
        .filter((p): p is number => p != null && p > 0),
    [forecastPoints],
  );

  const intradayBars = useMemo(() => {
    const series = finiteSparklinePoints(tickPoints);
    return ticksToIntradayBars(series, 40);
  }, [tickPoints]);

  const loadTicks = useCallback(async () => {
    const pathOnly = `/api/v1/symbols/${encodeURIComponent(symbol)}/snapshots`;
    if (!isSafeClientApiPath(pathOnly)) {
      setError("Invalid request path.");
      return;
    }
    const limit = sessionsForRange("1D");
    const res = await fetch(`${pathOnly}?limit=${limit}`, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      setError(`Could not load realtime ticks (${res.status}).`);
      return;
    }
    const body: unknown = await res.json();
    const raw =
      body != null &&
      typeof body === "object" &&
      !Array.isArray(body) &&
      Array.isArray((body as { points?: unknown }).points)
        ? (body as { points: unknown[] }).points
        : [];
    const out: Point[] = [];
    for (const row of raw) {
      if (row == null || typeof row !== "object" || Array.isArray(row)) continue;
      const r = row as Record<string, unknown>;
      const price = toFiniteNumber(r.price);
      if (price == null) continue;
      out.push({
        ts: typeof r.ts === "string" ? r.ts : null,
        price,
      });
    }
    // Snapshots API already returns ascending; re-sort defensively by time.
    const sorted =
      out.length >= 2
        ? [...out].sort((a, b) => {
            const ta = a.ts ? Date.parse(a.ts) : Number.POSITIVE_INFINITY;
            const tb = b.ts ? Date.parse(b.ts) : Number.POSITIVE_INFINITY;
            if (ta !== tb) return ta - tb;
            return 0;
          })
        : null;
    setFetchedTicks(sorted);
    setError(null);
    setLastRefresh(new Date().toISOString());
  }, [symbol]);

  const loadDaily = useCallback(
    async (r: Exclude<ChartRangeKey, "1D">) => {
      const limit = sessionsForRange(r);
      const pathOnly = `/api/v1/symbols/${encodeURIComponent(symbol)}/daily-bars`;
      if (!isSafeClientApiPath(pathOnly)) {
        setBars([]);
        setError("Invalid request path.");
        return;
      }
      const res = await fetch(`${pathOnly}?limit=${limit}`, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        setBars([]);
        setError(
          res.status === 404
            ? "Unknown symbol."
            : `Could not load daily path history (${res.status}).`,
        );
        return;
      }
      const body: unknown = await res.json();
      const raw =
        body != null &&
        typeof body === "object" &&
        !Array.isArray(body) &&
        Array.isArray((body as { bars?: unknown }).bars)
          ? (body as { bars: unknown[] }).bars
          : [];
      const out: DailyBarPoint[] = [];
      for (const row of raw) {
        if (row == null || typeof row !== "object" || Array.isArray(row)) {
          continue;
        }
        const b = row as Record<string, unknown>;
        const tradeDate =
          typeof b.trade_date === "string" ? b.trade_date.slice(0, 10) : null;
        const close = Number(b.close);
        const high = Number(b.high);
        const low = Number(b.low);
        const oRaw = b.open;
        const o = oRaw == null || oRaw === "" ? null : Number(oRaw);
        if (
          !tradeDate ||
          !Number.isFinite(close) ||
          !Number.isFinite(high) ||
          !Number.isFinite(low) ||
          (o != null && !Number.isFinite(o))
        ) {
          continue;
        }
        const vol = Number(b.volume);
        out.push({
          trade_date: tradeDate,
          open: o != null && o > 0 ? o : null,
          high,
          low,
          close,
          volume: Number.isFinite(vol) ? vol : null,
        });
      }
      if (out.length === 0) {
        setError("Daily bars response was empty.");
      } else {
        setError(null);
      }
      setBars(out);
      setLastRefresh(new Date().toISOString());
    },
    [symbol],
  );

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const run = async () => {
      setError(null);
      if (range === "1D") {
        setLoading(false);
        try {
          await loadTicks();
        } catch {
          if (!cancelled) setError("Could not refresh realtime ticks.");
        }
        return;
      }
      // Instant paint from SSR bars (tail for shorter ranges), then refresh.
      if (initialBars && initialBars.length > 0) {
        const limit = sessionsForRange(range);
        setBars(initialBars.slice(-limit));
        setLoading(false);
        setLastRefresh(new Date().toISOString());
      } else {
        setLoading(true);
      }
      try {
        await loadDaily(range);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [open, range, loadTicks, loadDaily, initialBars]);

  useEffect(() => {
    if (!open || range !== "1D") return;
    const id = window.setInterval(() => {
      void loadTicks();
    }, REALTIME_MS);
    return () => window.clearInterval(id);
  }, [open, range, loadTicks]);

  // Modal behaviour: Escape closes, page behind stays put, focus moves into
  // the dialog on open and returns to the expand trigger on close.
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const trigger = triggerRef.current;
    dialogRef.current?.focus();
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      trigger?.focus();
    };
  }, [open]);

  const modeLabel = range === "1D" ? "Intraday" : "Daily";
  const chartBars = range === "1D" ? intradayBars : bars;
  const tickSeries = finiteSparklinePoints(tickPoints);

  // Quote readout for the dialog header + window stats (Yahoo/Robinhood style:
  // last close, signed change over the *selected* range, window O/H/L/C).
  const windowStats = useMemo(() => {
    if (chartBars == null || chartBars.length < 2) return null;
    const first = chartBars[0]!;
    const last = chartBars[chartBars.length - 1]!;
    let high = -Infinity;
    let low = Infinity;
    for (const b of chartBars) {
      if (Number.isFinite(b.high)) high = Math.max(high, b.high);
      if (Number.isFinite(b.low)) low = Math.min(low, b.low);
      high = Math.max(high, b.close);
      low = Math.min(low, b.close);
    }
    if (!Number.isFinite(high) || !Number.isFinite(low)) return null;
    const change = last.close - first.close;
    const changePct = first.close > 0 ? (change / first.close) * 100 : null;
    return {
      lastClose: last.close,
      change,
      changePct,
      open: last.open,
      high,
      low,
      volume: last.volume,
      sessions: chartBars.length,
    };
  }, [chartBars]);

  return (
    <div className={className ?? "relative max-w-md"}>
      <div className="relative">
        <button
          type="button"
          ref={triggerRef}
          data-testid="expand-chart"
          className="absolute top-0 right-0 z-10 inline-flex h-8 items-center gap-1.5 rounded-full border border-border/70 bg-background/85 px-3 text-xs font-medium text-muted-foreground shadow-sm backdrop-blur transition-colors hover:border-border hover:text-foreground"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={open}
          title="Expand chart"
        >
          <Maximize2 className="size-3.5" aria-hidden />
          <span className="hidden sm:inline">Expand</span>
        </button>
        <SparklineWithForecast
          points={points}
          forecastPoints={forecastPoints}
          confidenceBand={confidenceBand}
          gate={gate}
          confidence={confidence}
          className="pr-16"
        />
      </div>

      {open ? (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/55 p-3 sm:p-6"
          role="presentation"
          data-testid="expand-chart-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            data-testid="expand-chart-dialog"
            ref={dialogRef}
            tabIndex={-1}
            className="flex h-[min(94vh,960px)] w-full max-w-[min(96vw,1400px)] flex-col overflow-hidden rounded-2xl border border-border bg-background shadow-2xl outline-none"
          >
            {/* Header — symbol + quote readout, close */}
            <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border/60 px-5 py-3.5">
              <div className="flex min-w-0 flex-wrap items-baseline gap-x-4 gap-y-1">
                <h2
                  id={titleId}
                  className="font-display text-xl font-semibold tracking-tight"
                >
                  {symbol}
                  <span className="ml-2 align-middle rounded-full border border-border/70 px-2 py-0.5 text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
                    {modeLabel}
                  </span>
                </h2>
                {windowStats ? (
                  <p className="flex min-w-0 flex-wrap items-baseline gap-x-2 font-mono tabular-nums">
                    <span className="text-xl font-semibold tracking-tight">
                      {formatNumber(windowStats.lastClose)}
                    </span>
                    <span
                      className={`text-sm font-medium ${
                        windowStats.change > 0
                          ? "text-emerald-700 dark:text-emerald-400"
                          : windowStats.change < 0
                            ? "text-rose-700 dark:text-rose-400"
                            : "text-muted-foreground"
                      }`}
                    >
                      {windowStats.change > 0 ? "+" : ""}
                      {formatNumber(windowStats.change)}
                      {windowStats.changePct != null
                        ? ` (${formatPct(windowStats.changePct)})`
                        : ""}
                      <span className="ml-1.5 font-sans text-xs font-normal text-muted-foreground">
                        {range}
                      </span>
                    </span>
                  </p>
                ) : null}
                {range === "1D" ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-800 dark:text-emerald-200">
                    <span
                      className="size-1.5 animate-pulse rounded-full bg-emerald-500"
                      aria-hidden
                    />
                    Live
                    {lastRefresh
                      ? ` · ${new Date(lastRefresh).toLocaleTimeString()}`
                      : ""}
                  </span>
                ) : null}
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="shrink-0"
                onClick={() => setOpen(false)}
                aria-label="Close chart"
              >
                <X className="size-4" />
              </Button>
            </div>

            {/* Toolbar — segmented range control + forecast toggle */}
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border/40 px-5 py-2.5">
              <div
                role="group"
                aria-label="Chart range"
                className="inline-flex items-center gap-0.5 rounded-lg border border-border/60 bg-muted/60 p-0.5"
              >
                {RANGES.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRange(r)}
                    aria-pressed={range === r}
                    className={
                      range === r
                        ? "rounded-md bg-background px-3 py-1.5 text-xs font-semibold text-foreground shadow-sm"
                        : "rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
                    }
                  >
                    {r}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  id={forecastToggleId}
                  type="button"
                  aria-pressed={showForecast}
                  disabled={forecastPrices.length === 0}
                  onClick={() => setShowForecast((v) => !v)}
                  title={
                    forecastPrices.length === 0
                      ? "No stored model forecast for this symbol."
                      : "Overlay the stored model forecast (dashed). Research only — not financial advice."
                  }
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${
                    showForecast && forecastPrices.length > 0
                      ? "border-sky-500/40 bg-sky-500/10 text-sky-800 dark:text-sky-200"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <span
                    className={`h-0 w-4 border-t-2 border-dashed ${
                      showForecast && forecastPrices.length > 0
                        ? "border-sky-600 dark:border-sky-400"
                        : "border-muted-foreground/60"
                    }`}
                    aria-hidden
                  />
                  Forecast
                  {forecastPrices.length === 0 ? " — none" : ""}
                </button>
              </div>
            </div>

            {/* Window stats — O/H/L/C over the selected range */}
            {windowStats ? (
              <dl className="flex shrink-0 flex-wrap items-baseline gap-x-6 gap-y-1 border-b border-border/40 px-5 py-2 font-mono text-xs tabular-nums">
                <WindowStat label="Open" value={formatNumber(windowStats.open)} />
                <WindowStat label="High" value={formatNumber(windowStats.high)} />
                <WindowStat label="Low" value={formatNumber(windowStats.low)} />
                <WindowStat
                  label="Close"
                  value={formatNumber(windowStats.lastClose)}
                />
                <WindowStat
                  label="Vol"
                  value={
                    windowStats.volume == null
                      ? "—"
                      : formatCompactNumber(Math.round(windowStats.volume), 1)
                  }
                />
                <span className="ml-auto font-sans text-[11px] text-muted-foreground">
                  {range === "1D"
                    ? "Intraday candles from live ticks — research only, not financial advice."
                    : "Green up / red down vs prior close — research only, not financial advice."}
                </span>
              </dl>
            ) : null}

            {/* Chart area — centered aspect box so candles aren't stretched */}
            <div className="flex min-h-0 flex-1 flex-col px-5 pt-3 pb-4">
              {loading ? (
                <div
                  className="flex min-h-0 flex-1 flex-col gap-2.5"
                  role="status"
                  aria-label="Loading chart"
                >
                  <div className="min-h-0 flex-1 animate-pulse rounded-xl border border-border/60 bg-muted/40" />
                  <div className="h-3 w-56 animate-pulse rounded bg-muted/60" />
                  <span className="sr-only">Loading chart…</span>
                </div>
              ) : error ? (
                <div className="flex min-h-0 flex-1 items-center justify-center rounded-xl border border-dashed border-border/60">
                  <p
                    className="max-w-sm text-center text-sm text-muted-foreground"
                    role="status"
                  >
                    {error}
                  </p>
                </div>
              ) : chartBars == null || chartBars.length < 2 ? (
                <div className="flex min-h-0 flex-1 items-center justify-center rounded-xl border border-dashed border-border/60">
                  <p
                    className="max-w-sm text-center text-sm text-muted-foreground"
                    role="status"
                  >
                    {range === "1D"
                      ? "Need more stored ticks for intraday candles."
                      : "No daily path history yet. On the host, run path-backfill, then refresh."}
                  </p>
                </div>
              ) : (
                <CandlestickChart
                  bars={chartBars}
                  fill
                  showForecast={showForecast}
                  forecastPrices={forecastPrices}
                  maxCandles={
                    range === "1D"
                      ? 60
                      : range === "1M"
                        ? 40
                        : range === "3M"
                          ? 90
                          : range === "6M"
                            ? 180
                            : 400 /* 1Y: every daily bar, scroll sideways */
                  }
                  className="min-h-0 flex-1"
                  footnote={
                    range === "1D"
                      ? `${tickSeries.length} live ticks → ${chartBars.length} intraday candles · research only`
                      : undefined
                  }
                />
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** Inline label/value pair for the dialog's O/H/L/C strip. */
function WindowStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <dt className="font-sans text-[11px] text-muted-foreground">{label}</dt>
      <dd className="font-medium text-foreground">{value}</dd>
    </div>
  );
}
