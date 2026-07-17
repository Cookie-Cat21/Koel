"use client";

import { useId, useState } from "react";

import { Sparkline } from "@/components/sparkline";
import { finiteSparklinePoints } from "@/lib/sparkline";
import { formatNumber } from "@/lib/format";

type Point = { ts: string | null; price: number | null | undefined };

function isSelectiveGate(gate: string | null | undefined): boolean {
  return (
    gate === "gated_p90" ||
    gate === "hpe_p90" ||
    gate === "gated_c55" ||
    gate === "gated"
  );
}

function gateBadgeMeta(gate: string | null | undefined): {
  label: string;
  title: string;
} | null {
  if (gate === "gated_p90" || gate === "hpe_p90") {
    return {
      label: "Selective ~90%",
      title:
        "Selective research emit — historical OOS ~90% when speaking (sparse). Not a guarantee. Not financial advice.",
    };
  }
  if (gate === "gated_c55" || gate === "gated") {
    return {
      label: "Selective ~73%",
      title:
        "Confidence-gated research emit — historical OOS ~73% when speaking. Not a guarantee. Not financial advice.",
    };
  }
  if (gate === "always_on") {
    return {
      label: "Always-on ~60%",
      title:
        "Always-on research estimate — historical hit ~60%. Not financial advice.",
    };
  }
  return null;
}

/**
 * Realtime sparkline with optional dashed forecast overlay.
 * Default = realtime only. Forecast is a model estimate — not advice.
 */
export function SparklineWithForecast({
  points,
  forecastPoints,
  className,
  confidenceBand,
  gate,
  confidence,
}: {
  points: Point[];
  forecastPoints?: Point[];
  className?: string;
  confidenceBand?: string | null;
  gate?: string | null;
  confidence?: number | null;
}) {
  const toggleId = useId();
  const series = finiteSparklinePoints(points);
  const forecast = finiteSparklinePoints(forecastPoints ?? []);
  const canToggle = forecast.length >= 1 && series.length >= 2;
  const spoke = canToggle;
  const bandLabel =
    confidenceBand === "high"
      ? "High"
      : confidenceBand === "medium"
        ? "Medium"
        : confidenceBand === "low"
          ? "Low"
          : null;
  const gateMeta = gateBadgeMeta(gate);
  // Auto-show selective / high-confidence overlays; user can still toggle off.
  const [showForecast, setShowForecast] = useState(
    () => isSelectiveGate(gate) || confidenceBand === "high",
  );

  if (series.length < 2) {
    return <Sparkline points={points} className={className} />;
  }

  const combinedPrices = [
    ...series.map((p) => p.price),
    ...(showForecast ? forecast.map((p) => p.price) : []),
  ];
  const min = Math.min(...combinedPrices);
  const max = Math.max(...combinedPrices);
  const span = Number.isFinite(max - min) && max !== min ? max - min : 1;
  const w = 320;
  const h = 72;
  const pad = 4;
  const totalN = series.length + (showForecast ? forecast.length : 0);

  const toCoord = (price: number, i: number, n: number) => {
    const x = pad + (i / Math.max(1, n - 1)) * (w - pad * 2);
    const y = pad + (1 - (price - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  };

  const realCoords = series.map((p, i) => toCoord(p.price, i, totalN));
  const forecastCoords =
    showForecast && forecast.length > 0
      ? [
          toCoord(series[series.length - 1]!.price, series.length - 1, totalN),
          ...forecast.map((p, i) => toCoord(p.price, series.length + i, totalN)),
        ]
      : [];

  const first = series[0]!.price;
  const last = series[series.length - 1]!.price;
  const up = last >= first;
  const aria = showForecast
    ? `Recent price from ${formatNumber(first)} to ${formatNumber(last)}, with model forecast overlay`
    : `Recent price from ${formatNumber(first)} to ${formatNumber(last)} across ${series.length} ticks`;

  return (
    <div className={className ?? "max-w-md"}>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-16 w-full"
        role="img"
        aria-label={aria}
      >
        <polyline
          fill="none"
          stroke={up ? "oklch(0.45 0.08 185)" : "oklch(0.5 0.1 25)"}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          points={realCoords.join(" ")}
        />
        {forecastCoords.length >= 2 ? (
          <polyline
            fill="none"
            stroke="oklch(0.55 0.04 250)"
            strokeWidth="2"
            strokeDasharray="4 3"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={forecastCoords.join(" ")}
          />
        ) : null}
      </svg>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {series.length} stored ticks · {formatNumber(first)} →{" "}
          {formatNumber(last)}
          {showForecast ? " · dashed = model estimate" : ""}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={
              spoke
                ? "rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium tracking-wide text-emerald-800 uppercase dark:text-emerald-200"
                : "rounded-full border border-border/70 px-2 py-0.5 text-[10px] font-medium tracking-wide text-muted-foreground uppercase"
            }
            title={
              spoke
                ? "Model spoke for this symbol (selective research emit). Not financial advice."
                : "Model stayed silent — no selective forecast stored for this symbol."
            }
          >
            {spoke ? "Spoke" : "Silent"}
          </span>
          {gateMeta ? (
            <span
              className="rounded-full border border-border/70 px-2 py-0.5 text-[10px] font-medium tracking-wide text-muted-foreground uppercase"
              title={gateMeta.title}
            >
              {gateMeta.label}
            </span>
          ) : null}
          {bandLabel ? (
            <span
              className="rounded-full border border-border/70 px-2 py-0.5 text-[10px] font-medium tracking-wide text-muted-foreground uppercase"
              title="Confidence band from historical OOS calibration — not a guarantee."
            >
              Confidence {bandLabel}
              {typeof confidence === "number" && Number.isFinite(confidence)
                ? ` · ${Math.round(confidence * 100)}%`
                : ""}
            </span>
          ) : null}
          {canToggle ? (
            <label
              htmlFor={toggleId}
              className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground"
            >
              <input
                id={toggleId}
                type="checkbox"
                className="size-3.5 rounded border-border"
                checked={showForecast}
                onChange={(e) => setShowForecast(e.target.checked)}
              />
              Show forecast
            </label>
          ) : (
            <span className="text-xs text-muted-foreground">
              Silent — no forecast stored
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
