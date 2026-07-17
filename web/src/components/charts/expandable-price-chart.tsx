"use client";

import { Maximize2, X } from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useState } from "react";

import { CandlestickChart } from "@/components/charts/candlestick-chart";
import { SparklineWithForecast } from "@/components/sparkline-with-forecast";
import { Button } from "@/components/ui/button";
import {
  type ChartRangeKey,
  type DailyBarPoint,
  sessionsForRange,
} from "@/lib/api/daily-bars";
import { isSafeClientApiPath } from "@/lib/api/client-fetch";
import { toFiniteNumber } from "@/lib/api/finite-number";
import { finiteSparklinePoints } from "@/lib/sparkline";
import { formatNumber } from "@/lib/format";

type Point = { ts: string | null; price: number | null | undefined };

const RANGES: ChartRangeKey[] = ["1D", "1M", "3M", "6M", "1Y"];
const REALTIME_MS = 20_000;

/**
 * Compact sparkline + corner expand → large chart dialog.
 * 1D = realtime ticks + forecast; longer ranges = daily candles.
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
  const [tickPoints, setTickPoints] = useState<Point[]>(points);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForecast, setShowForecast] = useState(
    () =>
      confidenceBand === "high" ||
      gate === "gated_p90" ||
      gate === "hpe_p90" ||
      gate === "gated_c55" ||
      gate === "gated",
  );
  const [lastRefresh, setLastRefresh] = useState<string | null>(null);

  const forecastPrices = useMemo(
    () =>
      (forecastPoints ?? [])
        .map((p) => toFiniteNumber(p.price))
        .filter((p): p is number => p != null && p > 0),
    [forecastPoints],
  );

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
    setTickPoints(out.length >= 2 ? out : points);
    setError(null);
    setLastRefresh(new Date().toISOString());
  }, [symbol, points]);

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

  // Keep compact sparkline ticks in sync when parent refreshes.
  useEffect(() => {
    if (range === "1D") setTickPoints(points);
  }, [points, range]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const run = async () => {
      setError(null);
      if (range === "1D") {
        // Show known ticks immediately; refresh in background.
        setTickPoints(points);
        setLoading(false);
        try {
          await loadTicks();
        } catch {
          if (!cancelled) setError("Could not refresh realtime ticks.");
        }
        return;
      }
      if (range === "1Y" && initialBars && initialBars.length > 0) {
        setBars(initialBars);
        setLoading(false);
        setLastRefresh(new Date().toISOString());
        return;
      }
      setLoading(true);
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
  }, [open, range, loadTicks, loadDaily, initialBars, points]);

  // Realtime poll while 1D expand is open
  useEffect(() => {
    if (!open || range !== "1D") return;
    const id = window.setInterval(() => {
      void loadTicks();
    }, REALTIME_MS);
    return () => window.clearInterval(id);
  }, [open, range, loadTicks]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const tickSeries = finiteSparklinePoints(tickPoints);
  const modeLabel = range === "1D" ? "Realtime" : "Daily";

  return (
    <div className={className ?? "relative max-w-md"}>
      <div className="relative">
        <button
          type="button"
          data-testid="expand-chart"
          className="absolute top-0 right-0 z-10 inline-flex h-8 items-center gap-1 rounded-md border border-border bg-background px-2 text-xs font-medium text-foreground shadow-sm hover:bg-muted/50"
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
          className="fixed inset-0 z-[100] flex items-stretch justify-center bg-black/50 p-2 sm:items-center sm:p-4"
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
            className="flex h-[min(94vh,920px)] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-border bg-background shadow-xl"
          >
            <div className="flex items-start justify-between gap-3 border-b border-border/60 px-4 py-3 sm:px-5">
              <div className="min-w-0">
                <h2
                  id={titleId}
                  className="font-display text-lg font-semibold tracking-tight sm:text-xl"
                >
                  {symbol} · {modeLabel}
                </h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {range === "1D"
                    ? "Realtime ticks from price snapshots — research only, not financial advice."
                    : "Green up / red down vs prior close (CSE often omits open) — research only, not financial advice."}
                </p>
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

            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/40 px-4 py-2 sm:px-5">
              <div className="flex flex-wrap gap-2">
                {RANGES.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRange(r)}
                    className={
                      range === r
                        ? "rounded-full border border-foreground/30 bg-muted px-3 py-1 text-xs font-medium"
                        : "rounded-full border border-border/70 px-3 py-1 text-xs text-muted-foreground hover:bg-muted/50"
                    }
                  >
                    {r}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <label
                  htmlFor={forecastToggleId}
                  className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground"
                >
                  <input
                    id={forecastToggleId}
                    type="checkbox"
                    className="size-3.5 rounded border-border"
                    checked={showForecast}
                    onChange={(e) => setShowForecast(e.target.checked)}
                    disabled={forecastPrices.length === 0}
                  />
                  Show forecast
                  {forecastPrices.length === 0 ? " (none)" : ""}
                </label>
                {range === "1D" ? (
                  <span className="text-[11px] text-muted-foreground">
                    Live · refresh {REALTIME_MS / 1000}s
                    {lastRefresh
                      ? ` · ${new Date(lastRefresh).toLocaleTimeString()}`
                      : ""}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-5">
              {loading ? (
                <p className="text-sm text-muted-foreground" role="status">
                  Loading chart…
                </p>
              ) : error ? (
                <p className="text-sm text-muted-foreground" role="status">
                  {error}
                </p>
              ) : range === "1D" ? (
                tickSeries.length < 2 ? (
                  <p className="text-sm text-muted-foreground" role="status">
                    Need two stored ticks for realtime view.
                  </p>
                ) : (
                  <div className="mx-auto max-w-5xl">
                    <RealtimeExpandChart
                      points={tickPoints}
                      forecastPoints={
                        showForecast ? forecastPoints : undefined
                      }
                    />
                    <p className="mt-2 text-xs text-muted-foreground">
                      {tickSeries.length} ticks ·{" "}
                      {formatNumber(tickSeries[0]!.price)} →{" "}
                      {formatNumber(tickSeries[tickSeries.length - 1]!.price)}
                      {showForecast && forecastPrices.length > 0
                        ? " · dashed = model forecast"
                        : ""}{" "}
                      · research only
                    </p>
                  </div>
                )
              ) : bars == null || bars.length === 0 ? (
                <p className="text-sm text-muted-foreground" role="status">
                  No daily path history yet. On the host, run path-backfill,
                  then refresh.
                </p>
              ) : (
                <CandlestickChart
                  bars={bars}
                  height={480}
                  showForecast={showForecast}
                  forecastPrices={forecastPrices}
                />
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** Larger line chart for 1D expand (ticks + optional forecast). */
function RealtimeExpandChart({
  points,
  forecastPoints,
}: {
  points: Point[];
  forecastPoints?: Point[];
}) {
  const series = finiteSparklinePoints(points);
  const forecast = finiteSparklinePoints(forecastPoints ?? []);
  if (series.length < 2) return null;

  const combined = [
    ...series.map((p) => p.price),
    ...forecast.map((p) => p.price),
  ];
  const min = Math.min(...combined);
  const max = Math.max(...combined);
  const span = max !== min ? max - min : 1;
  const w = 960;
  const h = 420;
  const pad = 12;
  const totalN = series.length + (forecast.length > 0 ? forecast.length : 0);

  const toCoord = (price: number, i: number) => {
    const x = pad + (i / Math.max(1, totalN - 1)) * (w - pad * 2);
    const y = pad + (1 - (price - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  };

  const realCoords = series.map((p, i) => toCoord(p.price, i));
  const first = series[0]!.price;
  const last = series[series.length - 1]!.price;
  const up = last >= first;
  const forecastCoords =
    forecast.length > 0
      ? [
          toCoord(last, series.length - 1),
          ...forecast.map((p, i) => toCoord(p.price, series.length + i)),
        ]
      : [];

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-auto w-full max-h-[55vh]"
      role="img"
      aria-label={`Realtime price from ${formatNumber(first)} to ${formatNumber(last)}`}
    >
      <rect
        x={0}
        y={0}
        width={w}
        height={h}
        className="fill-muted/20"
        rx={8}
      />
      <polyline
        fill="none"
        stroke={up ? "oklch(0.45 0.08 185)" : "oklch(0.5 0.1 25)"}
        strokeWidth="2.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={realCoords.join(" ")}
      />
      {forecastCoords.length >= 2 ? (
        <polyline
          fill="none"
          stroke="oklch(0.55 0.04 250)"
          strokeWidth="2.5"
          strokeDasharray="6 4"
          strokeLinejoin="round"
          strokeLinecap="round"
          points={forecastCoords.join(" ")}
        />
      ) : null}
    </svg>
  );
}
