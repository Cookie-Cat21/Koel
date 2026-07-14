"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import { Button } from "@/components/ui/button";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  CLIENT_API_BODY_MAX_CHARS,
  CLIENT_API_TIMEOUT_MS,
  apiErrorMessage,
} from "@/lib/api/client-fetch";
import { readBoundedResponseText } from "@/lib/api/read-bounded-text";
import { normalizeSymbol } from "@/lib/api/symbol";
import {
  MAX_COMPARE_SYMBOLS,
  buildCompareChartRows,
  compareSeriesKey,
  type CompareScaleMode,
  type CompareSeries,
} from "@/lib/compare-chart";
import { formatNumber } from "@/lib/format";
import { finiteSparklinePoints } from "@/lib/sparkline";
import { cn } from "@/lib/utils";

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
] as const;

const SCALE_OPTIONS = [1, 2, 3, 4] as const;

type Props = {
  baseSymbol: string;
  /** SSR ticks for the base symbol — chart works even if peer fetch is slow. */
  initialPoints?: { ts: string | null; price: number | null | undefined }[];
  className?: string;
};

function parseComparePayload(body: unknown): CompareSeries[] {
  if (!body || typeof body !== "object" || Array.isArray(body)) return [];
  const raw = (body as { series?: unknown }).series;
  if (!Array.isArray(raw)) return [];
  const out: CompareSeries[] = [];
  for (const row of raw) {
    if (out.length >= MAX_COMPARE_SYMBOLS) break;
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const r = row as Record<string, unknown>;
    const symbol = normalizeSymbol(r.symbol);
    if (!symbol) continue;
    const pointsRaw = r.points;
    if (!Array.isArray(pointsRaw)) continue;
    const points = pointsRaw.flatMap((p) => {
      if (!p || typeof p !== "object" || Array.isArray(p)) return [];
      const point = p as Record<string, unknown>;
      const price =
        typeof point.price === "number" && Number.isFinite(point.price)
          ? point.price
          : null;
      if (price == null) return [];
      return [
        {
          ts: typeof point.ts === "string" ? point.ts : null,
          price,
        },
      ];
    });
    out.push({ symbol, points });
  }
  return out;
}

export function SymbolCompareChart({
  baseSymbol,
  initialPoints = [],
  className,
}: Props) {
  const base = normalizeSymbol(baseSymbol) ?? baseSymbol.toUpperCase();
  const scaleGroupId = useId();
  const modeGroupId = useId();
  const peerId = useId();

  const baseSeries = useMemo<CompareSeries>(() => {
    return {
      symbol: base,
      points: finiteSparklinePoints(initialPoints),
    };
  }, [base, initialPoints]);

  const [scale, setScale] = useState<(typeof SCALE_OPTIONS)[number]>(1);
  const [mode, setMode] = useState<CompareScaleMode>("indexed");
  const [peers, setPeers] = useState<string[]>(["", "", ""]);
  const [draft, setDraft] = useState("");
  const [peerSeries, setPeerSeries] = useState<CompareSeries[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedPeers = useMemo(() => {
    const list: string[] = [];
    for (let i = 0; i < scale - 1; i++) {
      const peer = normalizeSymbol(peers[i] ?? "");
      if (peer && peer !== base && !list.includes(peer)) list.push(peer);
    }
    return list.slice(0, MAX_COMPARE_SYMBOLS - 1);
  }, [base, peers, scale]);

  const selectedSymbols = useMemo(
    () => [base, ...selectedPeers].slice(0, MAX_COMPARE_SYMBOLS),
    [base, selectedPeers],
  );

  const peerKey = selectedPeers.join(",");

  useEffect(() => {
    if (!peerKey) {
      setPeerSeries([]);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), CLIENT_API_TIMEOUT_MS);

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const qs = new URLSearchParams({
          symbols: [base, ...peerKey.split(",")].join(","),
          limit: "60",
        });
        const res = await fetch(`/api/v1/compare?${qs.toString()}`, {
          credentials: "same-origin",
          signal: ctrl.signal,
        });
        const bounded = await readBoundedResponseText(
          res,
          CLIENT_API_BODY_MAX_CHARS,
        );
        if (!bounded.ok) {
          if (!cancelled) {
            setPeerSeries([]);
            setError("Couldn’t load compare series.");
          }
          return;
        }
        let body: unknown = null;
        try {
          body = bounded.text ? JSON.parse(bounded.text) : null;
        } catch {
          body = null;
        }
        if (!res.ok) {
          if (!cancelled) {
            setPeerSeries([]);
            setError(apiErrorMessage(body, "Couldn’t load compare series."));
          }
          return;
        }
        if (!cancelled) {
          const parsed = parseComparePayload(body).filter(
            (s) => s.symbol !== base,
          );
          setPeerSeries(parsed);
        }
      } catch {
        if (!cancelled) {
          setPeerSeries([]);
          setError("Couldn’t load compare series.");
        }
      } finally {
        clearTimeout(timer);
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
      ctrl.abort();
      clearTimeout(timer);
    };
  }, [base, peerKey]);

  const series = useMemo(() => {
    if (selectedPeers.length === 0) return [baseSeries];
    const bySymbol = new Map(peerSeries.map((s) => [s.symbol, s]));
    const peersResolved = selectedPeers.map(
      (symbol) => bySymbol.get(symbol) ?? { symbol, points: [] },
    );
    return [baseSeries, ...peersResolved];
  }, [baseSeries, peerSeries, selectedPeers]);

  const chartConfig = useMemo(() => {
    const cfg: ChartConfig = {};
    selectedSymbols.forEach((symbol, i) => {
      cfg[compareSeriesKey(symbol)] = {
        label: symbol,
        color: CHART_COLORS[i % CHART_COLORS.length],
      };
    });
    return cfg;
  }, [selectedSymbols]);

  const rows = useMemo(
    () => buildCompareChartRows(series, mode),
    [series, mode],
  );

  const needsPeers = scale > 1;
  const showChart =
    rows.length >= 2 && (!needsPeers || selectedPeers.length >= 1);

  function addPeerFromDraft() {
    const next = normalizeSymbol(draft);
    if (!next || next === base) {
      setError("Enter a different listed symbol (e.g. COMB.N0000).");
      return;
    }
    if (selectedSymbols.includes(next) || peers.includes(next)) {
      setError("That symbol is already on the chart.");
      return;
    }
    const slot = peers.findIndex((p) => !normalizeSymbol(p));
    if (slot < 0 || selectedSymbols.length >= MAX_COMPARE_SYMBOLS) {
      setError(`Max ${MAX_COMPARE_SYMBOLS} companies.`);
      return;
    }
    const nextPeers = [...peers];
    nextPeers[slot] = next;
    setPeers(nextPeers);
    setDraft("");
    setError(null);
    if (scale < slot + 2) {
      setScale((SCALE_OPTIONS[slot + 1] ?? 4) as (typeof SCALE_OPTIONS)[number]);
    }
  }

  function clearPeer(index: number) {
    setPeers((prev) => {
      const next = [...prev];
      next[index] = "";
      return next;
    });
  }

  return (
    <section
      className={cn("mt-8 border-t border-border/60 pt-6", className)}
      aria-labelledby="compare-heading"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2
            id="compare-heading"
            className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
          >
            Price compare
          </h2>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Overlay up to {MAX_COMPARE_SYMBOLS} listed symbols from stored
            ticks. Indexed mode starts each line at 100 so different price
            levels stay readable. Not financial advice.
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-4">
        <fieldset className="min-w-0">
          <legend className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Scale (companies)
          </legend>
          <div
            className="mt-2 flex flex-wrap gap-2"
            role="radiogroup"
            aria-labelledby={scaleGroupId}
          >
            <span id={scaleGroupId} className="sr-only">
              Number of companies
            </span>
            {SCALE_OPTIONS.map((n) => (
              <Button
                key={n}
                type="button"
                size="sm"
                variant={scale === n ? "default" : "outline"}
                aria-pressed={scale === n}
                onClick={() => setScale(n)}
              >
                {n}
              </Button>
            ))}
          </div>
        </fieldset>

        <fieldset className="min-w-0">
          <legend className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Y axis
          </legend>
          <div
            className="mt-2 flex flex-wrap gap-2"
            role="radiogroup"
            aria-labelledby={modeGroupId}
          >
            <span id={modeGroupId} className="sr-only">
              Chart scale mode
            </span>
            <Button
              type="button"
              size="sm"
              variant={mode === "indexed" ? "default" : "outline"}
              aria-pressed={mode === "indexed"}
              onClick={() => setMode("indexed")}
            >
              Indexed (100)
            </Button>
            <Button
              type="button"
              size="sm"
              variant={mode === "price" ? "default" : "outline"}
              aria-pressed={mode === "price"}
              onClick={() => setMode("price")}
            >
              Price (LKR)
            </Button>
          </div>
        </fieldset>

        {needsPeers ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-md border border-border/70 bg-muted/30 px-2.5 py-1 font-mono text-xs">
                {base}
              </span>
              {peers.slice(0, scale - 1).map((peer, i) => {
                const normalized = normalizeSymbol(peer);
                if (!normalized) return null;
                return (
                  <button
                    key={`${normalized}-${i}`}
                    type="button"
                    className="rounded-md border border-border/70 px-2.5 py-1 font-mono text-xs hover:bg-muted/40"
                    onClick={() => clearPeer(i)}
                    title="Remove from compare"
                  >
                    {normalized} ×
                  </button>
                );
              })}
            </div>
            {selectedSymbols.length < scale ? (
              <div className="flex max-w-md flex-col gap-2 sm:flex-row sm:items-end">
                <div className="min-w-0 flex-1">
                  <Label htmlFor={peerId}>Add company</Label>
                  <Input
                    id={peerId}
                    className="mt-1 font-mono"
                    placeholder="e.g. COMB.N0000"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value.toUpperCase())}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addPeerFromDraft();
                      }
                    }}
                    autoComplete="off"
                    spellCheck={false}
                  />
                </div>
                <Button type="button" size="sm" onClick={addPeerFromDraft}>
                  Add
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}

        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}

        {loading ? (
          <p className="text-sm text-muted-foreground" role="status">
            Loading peer ticks…
          </p>
        ) : null}

        {!loading && needsPeers && selectedPeers.length === 0 ? (
          <p className="text-sm text-muted-foreground" role="status">
            Add {scale - 1} more compan{scale - 1 === 1 ? "y" : "ies"} to fill
            this scale (max {MAX_COMPARE_SYMBOLS}).
          </p>
        ) : null}

        {showChart ? (
          <ChartContainer
            config={chartConfig}
            className="aspect-auto h-64 w-full"
          >
            <LineChart
              accessibilityLayer
              data={rows}
              margin={{ left: 8, right: 8, top: 8, bottom: 0 }}
            >
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="t"
                tickLine={false}
                axisLine={false}
                minTickGap={28}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                width={48}
                tickFormatter={(v) =>
                  mode === "indexed"
                    ? formatNumber(Number(v), 0)
                    : formatNumber(Number(v), 1)
                }
              />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    labelFormatter={(_, payload) => {
                      const first = payload?.[0]?.payload as
                        | { ts?: string | null }
                        | undefined;
                      return first?.ts ? String(first.ts) : "";
                    }}
                  />
                }
              />
              <ChartLegend content={<ChartLegendContent />} />
              {selectedSymbols.map((symbol) => {
                const key = compareSeriesKey(symbol);
                return (
                  <Line
                    key={key}
                    dataKey={key}
                    name={symbol}
                    type="monotone"
                    stroke={`var(--color-${key})`}
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                );
              })}
            </LineChart>
          </ChartContainer>
        ) : !loading && !needsPeers ? (
          <p className="text-sm text-muted-foreground" role="status">
            Need at least two stored ticks for {base}.
          </p>
        ) : null}
      </div>
    </section>
  );
}
