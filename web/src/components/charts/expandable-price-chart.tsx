"use client";

import { Maximize2, X } from "lucide-react";
import { useCallback, useEffect, useId, useState } from "react";

import { CandlestickChart } from "@/components/charts/candlestick-chart";
import { SparklineWithForecast } from "@/components/sparkline-with-forecast";
import { Button } from "@/components/ui/button";
import {
  type DailyBarPoint,
  sessionsForRange,
} from "@/lib/api/daily-bars";
import { isSafeClientApiPath } from "@/lib/api/client-fetch";

type Point = { ts: string | null; price: number | null | undefined };
type RangeKey = "1M" | "3M" | "6M" | "1Y";

const RANGES: RangeKey[] = ["1M", "3M", "6M", "1Y"];

/**
 * Compact sparkline + corner expand control → daily candlestick dialog.
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
}: {
  symbol: string;
  points: Point[];
  forecastPoints?: Point[];
  confidenceBand?: string | null;
  gate?: string | null;
  confidence?: number | null;
  className?: string;
  /** Open expand dialog on mount (e.g. ``?expandChart=1``). */
  initialOpen?: boolean;
  /** Optional SSR-provided bars (skips first client fetch when set). */
  initialBars?: DailyBarPoint[] | null;
}) {
  const titleId = useId();
  const [open, setOpen] = useState(Boolean(initialOpen));
  const [range, setRange] = useState<RangeKey>("1Y");
  const [bars, setBars] = useState<DailyBarPoint[] | null>(initialBars);
  const [loading, setLoading] = useState(
    Boolean(initialOpen) && !(initialBars && initialBars.length > 0),
  );
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (r: RangeKey) => {
      setLoading(true);
      setError(null);
      try {
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
          const o = Number(b.open);
          const high = Number(b.high);
          const low = Number(b.low);
          const close = Number(b.close);
          if (
            !tradeDate ||
            !Number.isFinite(o) ||
            !Number.isFinite(high) ||
            !Number.isFinite(low) ||
            !Number.isFinite(close)
          ) {
            continue;
          }
          const vol = Number(b.volume);
          out.push({
            trade_date: tradeDate,
            open: o,
            high,
            low,
            close,
            volume: Number.isFinite(vol) ? vol : null,
          });
        }
        if (out.length === 0) {
          setError("Daily bars response was empty.");
        }
        setBars(out);
      } catch {
        setBars([]);
        setError("Could not load daily path history.");
      } finally {
        setLoading(false);
      }
    },
    [symbol],
  );

  useEffect(() => {
    if (!open) return;
    if (range === "1Y" && initialBars && initialBars.length > 0) {
      setBars(initialBars);
      setLoading(false);
      setError(null);
      return;
    }
    void load(range);
  }, [open, range, load, initialBars]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

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
          title="Expand daily candlestick chart"
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
          className="fixed inset-0 z-[100] flex items-end justify-center bg-black/40 p-4 sm:items-center"
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
            className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-border bg-background shadow-lg"
          >
            <div className="flex items-start justify-between gap-3 border-b border-border/60 px-4 py-3">
              <div className="min-w-0">
                <h2
                  id={titleId}
                  className="font-display text-lg font-semibold tracking-tight"
                >
                  {symbol} · Daily
                </h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Green up / red down candlesticks from path history — research
                  only, not financial advice.
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

            <div className="flex flex-wrap gap-2 border-b border-border/40 px-4 py-2">
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

            <div className="overflow-y-auto px-4 py-4">
              {loading ? (
                <p className="text-sm text-muted-foreground" role="status">
                  Loading daily bars…
                </p>
              ) : error ? (
                <p className="text-sm text-muted-foreground" role="status">
                  {error}
                </p>
              ) : bars == null || bars.length === 0 ? (
                <p className="text-sm text-muted-foreground" role="status">
                  No daily path history yet. On the host, run path-backfill,
                  then refresh.
                </p>
              ) : (
                <CandlestickChart bars={bars} />
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
