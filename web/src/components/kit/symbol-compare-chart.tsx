"use client";

import { useEffect, useId, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
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

/** Tremor / shadcn chart-1..4 tokens — multi-series overlay. */
const SERIES_STROKES = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
] as const;

const SCALE_OPTIONS = [1, 2, 3, 4] as const;

type Props = {
  baseSymbol: string;
  /** SSR ticks for the base symbol — chart paints without a client fetch. */
  initialPoints?: { ts: string | null; price: number | null | undefined }[];
  /** Optional SSR peer series (e.g. from ?compare=) so overlays paint without hydration. */
  initialPeerSeries?: CompareSeries[];
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

type PolySeries = {
  symbol: string;
  key: string;
  stroke: string;
  pointsAttr: string;
};

function buildSvgPolylines(
  symbols: string[],
  rows: ReturnType<typeof buildCompareChartRows>,
): {
  series: PolySeries[];
  yTicks: { y: number; label: string }[];
  xTicks: { x: number; label: string }[];
  width: number;
  height: number;
  plot: { left: number; top: number; right: number; bottom: number };
} | null {
  if (rows.length < 2 || symbols.length < 1) return null;

  const width = 640;
  const height = 240;
  const plot = { left: 48, top: 16, right: 16, bottom: 32 };
  const plotW = width - plot.left - plot.right;
  const plotH = height - plot.top - plot.bottom;

  const keys = symbols.map(compareSeriesKey);
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const row of rows) {
    for (const key of keys) {
      const v = row[key];
      if (typeof v === "number" && Number.isFinite(v)) {
        min = Math.min(min, v);
        max = Math.max(max, v);
      }
    }
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
  const span = max !== min ? max - min : 1;

  const series: PolySeries[] = symbols.map((symbol, si) => {
    const key = keys[si]!;
    const coords: string[] = [];
    for (let i = 0; i < rows.length; i++) {
      const v = rows[i]![key];
      if (typeof v !== "number" || !Number.isFinite(v)) continue;
      const x = plot.left + (i / (rows.length - 1)) * plotW;
      const y = plot.top + (1 - (v - min) / span) * plotH;
      coords.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    return {
      symbol,
      key,
      stroke: SERIES_STROKES[si % SERIES_STROKES.length]!,
      pointsAttr: coords.join(" "),
    };
  });

  if (series.some((s) => s.pointsAttr.split(" ").length < 2)) {
    // Allow partial peers; require at least one drawable series.
    if (!series.some((s) => s.pointsAttr.split(" ").length >= 2)) return null;
  }

  const yTicks = [0, 0.5, 1].map((t) => {
    const value = max - t * span;
    return {
      y: plot.top + t * plotH,
      label: formatNumber(value, span >= 20 ? 0 : 1),
    };
  });

  const xIdx = [0, Math.floor((rows.length - 1) / 2), rows.length - 1];
  const xTicks = xIdx.map((i) => ({
    x: plot.left + (i / (rows.length - 1)) * plotW,
    label: String(rows[i]?.t ?? ""),
  }));

  return { series, yTicks, xTicks, width, height, plot };
}

function clampScale(n: number): (typeof SCALE_OPTIONS)[number] {
  if (n <= 1) return 1;
  if (n === 2) return 2;
  if (n === 3) return 3;
  return 4;
}

export function SymbolCompareChart({
  baseSymbol,
  initialPoints = [],
  initialPeerSeries = [],
  className,
}: Props) {
  const base = normalizeSymbol(baseSymbol) ?? baseSymbol.toUpperCase();
  const scaleGroupId = useId();
  const modeGroupId = useId();
  const peerId = useId();
  const titleId = useId();

  const baseSeries = useMemo<CompareSeries>(() => {
    return {
      symbol: base,
      points: finiteSparklinePoints(initialPoints),
    };
  }, [base, initialPoints]);

  const ssrPeers = useMemo(() => {
    const list: string[] = [];
    for (const row of initialPeerSeries) {
      const symbol = normalizeSymbol(row.symbol);
      if (!symbol || symbol === base || list.includes(symbol)) continue;
      list.push(symbol);
      if (list.length >= MAX_COMPARE_SYMBOLS - 1) break;
    }
    return list;
  }, [base, initialPeerSeries]);

  const [scale, setScale] = useState<(typeof SCALE_OPTIONS)[number]>(() =>
    clampScale(1 + ssrPeers.length),
  );
  const [mode, setMode] = useState<CompareScaleMode>("indexed");
  const [peers, setPeers] = useState<string[]>(() => {
    const slots = ["", "", ""];
    ssrPeers.forEach((symbol, i) => {
      if (i < 3) slots[i] = symbol;
    });
    return slots;
  });
  const [draft, setDraft] = useState("");
  const [peerSeries, setPeerSeries] =
    useState<CompareSeries[]>(initialPeerSeries);
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
    // Empty peerKey: series useMemo already falls back to base-only — no
    // sync setState (react-hooks/set-state-in-effect).
    if (!peerKey) return;

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
          setPeerSeries(
            parseComparePayload(body).filter((s) => s.symbol !== base),
          );
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

  const rows = useMemo(
    () => buildCompareChartRows(series, mode),
    [series, mode],
  );

  const svg = useMemo(
    () => buildSvgPolylines(selectedSymbols, rows),
    [selectedSymbols, rows],
  );

  const needsPeers = scale > 1;
  const showChart =
    svg != null && (!needsPeers || selectedPeers.length >= 1);

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
      <div>
        <h2
          id="compare-heading"
          className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
        >
          Price compare
        </h2>
        <p className="mt-1 max-w-xl text-sm text-muted-foreground">
          Overlay up to {MAX_COMPARE_SYMBOLS} listed symbols from stored ticks.
          Indexed mode starts each line at 100 so different price levels stay
          readable. Not financial advice.
        </p>
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

        {showChart && svg ? (
          <div className="rounded-lg border border-border/70 bg-muted/15 p-3">
            <ul className="mb-2 flex flex-wrap gap-3" aria-label="Series legend">
              {svg.series.map((s) => (
                <li
                  key={s.key}
                  className="flex items-center gap-2 font-mono text-xs"
                >
                  <span
                    className="inline-block size-2.5 rounded-full"
                    style={{ background: s.stroke }}
                    aria-hidden
                  />
                  {s.symbol}
                </li>
              ))}
            </ul>
            <svg
              viewBox={`0 0 ${svg.width} ${svg.height}`}
              className="h-56 w-full"
              role="img"
              aria-labelledby={titleId}
            >
              <title id={titleId}>
                Price compare for {selectedSymbols.join(", ")} (
                {mode === "indexed" ? "indexed to 100" : "LKR"})
              </title>
              {svg.yTicks.map((tick) => (
                <g key={`y-${tick.y}`}>
                  <line
                    x1={svg.plot.left}
                    x2={svg.width - svg.plot.right}
                    y1={tick.y}
                    y2={tick.y}
                    stroke="currentColor"
                    strokeOpacity={0.12}
                  />
                  <text
                    x={svg.plot.left - 8}
                    y={tick.y + 3}
                    textAnchor="end"
                    className="fill-muted-foreground"
                    fontSize="10"
                  >
                    {tick.label}
                  </text>
                </g>
              ))}
              {svg.xTicks.map((tick) => (
                <text
                  key={`x-${tick.x}-${tick.label}`}
                  x={tick.x}
                  y={svg.height - 10}
                  textAnchor="middle"
                  className="fill-muted-foreground"
                  fontSize="10"
                >
                  {tick.label}
                </text>
              ))}
              {svg.series.map((s) =>
                s.pointsAttr.split(" ").length >= 2 ? (
                  <polyline
                    key={s.key}
                    fill="none"
                    stroke={s.stroke}
                    strokeWidth="2.25"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    points={s.pointsAttr}
                  />
                ) : null,
              )}
            </svg>
            <p className="mt-1 text-xs text-muted-foreground">
              {mode === "indexed"
                ? "Y axis: indexed (first tick = 100)."
                : "Y axis: last price (LKR)."}{" "}
              Stored poller ticks only — not financial advice.
            </p>
          </div>
        ) : !loading && !needsPeers ? (
          <p className="text-sm text-muted-foreground" role="status">
            Need at least two stored ticks for {base}.
          </p>
        ) : null}
      </div>
    </section>
  );
}
