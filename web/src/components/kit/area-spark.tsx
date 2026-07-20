"use client";

import { useId, useMemo, useRef } from "react";

import { useChartHover } from "@/hooks/use-chart-hover";
import {
  AREA_SPARK_STROKE,
  toneFromSeries,
  type AreaSparkTone,
} from "@/lib/area-spark";
import { buildChartGeometry } from "@/lib/chart-geometry";
import { cn } from "@/lib/utils";

/**
 * Tremor-style area spark — gradient fill + polyline.
 * Set ``interactive`` for hover crosshair, tooltip, and arrow-key scrubbing.
 */
export function AreaSpark({
  values,
  labels,
  tone,
  upIsGood = true,
  className,
  heightClass = "h-14",
  ariaLabel,
  interactive = false,
  formatValue,
}: {
  values: Array<number | null | undefined>;
  /** Optional per-point labels (dates) aligned to finite ``values`` after filter. */
  labels?: Array<string | null | undefined>;
  tone?: AreaSparkTone;
  upIsGood?: boolean;
  className?: string;
  heightClass?: string;
  ariaLabel?: string;
  interactive?: boolean;
  formatValue?: (n: number) => string;
}) {
  const gid = useId();
  const svgRef = useRef<SVGSVGElement | null>(null);
  // Zip value+label before dropping non-finite so hover dates stay aligned.
  const paired = useMemo(() => {
    const out: { value: number; label: string | null }[] = [];
    for (let i = 0; i < values.length; i++) {
      const v = values[i];
      if (typeof v !== "number" || !Number.isFinite(v)) continue;
      const lab = labels?.[i];
      out.push({
        value: v,
        label: typeof lab === "string" && lab.trim() ? lab.trim() : null,
      });
    }
    return out;
  }, [values, labels]);
  const series = useMemo(() => paired.map((p) => p.value), [paired]);
  const alignedLabels = useMemo(() => paired.map((p) => p.label), [paired]);
  const geo = useMemo(() => buildChartGeometry(series), [series]);

  const points = geo?.points ?? [];
  const {
    activeIndex,
    onPointerMove,
    onPointerLeave,
    onPointerDown,
    onKeyDown,
    onFocus,
    onBlur,
  } = useChartHover(
    svgRef,
    points,
    geo?.width ?? 240,
    interactive && points.length >= 2,
  );

  if (!geo || series.length < 2) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-md bg-muted/40 text-[10px] text-muted-foreground",
          heightClass,
          className,
        )}
        role="status"
      >
        Not enough points
      </div>
    );
  }

  const resolved = tone ?? toneFromSeries(series, upIsGood);
  const stroke = AREA_SPARK_STROKE[resolved];
  const last = geo.points[geo.points.length - 1]!;
  const active =
    interactive && activeIndex != null
      ? geo.points[activeIndex] ?? null
      : null;
  const activeLabel =
    interactive && activeIndex != null
      ? alignedLabels[activeIndex] ?? null
      : null;
  const fmt =
    formatValue ??
    ((n: number) => {
      if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
      if (Math.abs(n) >= 1e3)
        return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
      return Number.isInteger(n) ? String(n) : n.toFixed(2);
    });

  const tipText = active
    ? `${activeLabel ? `${activeLabel} · ` : ""}${fmt(active.value)}`
    : null;

  const tipX = active
    ? Math.min(Math.max(active.x, 36), geo.width - 36)
    : 0;
  const tipY = active ? Math.max(14, active.y - 10) : 0;

  return (
    <div className={cn("relative w-full", className)}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${geo.width} ${geo.height}`}
        preserveAspectRatio="none"
        className={cn(
          "w-full outline-none",
          heightClass,
          interactive &&
            "cursor-crosshair rounded-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
        )}
        role="img"
        aria-label={
          ariaLabel ??
          `Sparkline, ${series.length} points${
            interactive ? ". Arrow keys scrub points." : ""
          }`
        }
        tabIndex={interactive ? 0 : undefined}
        onPointerMove={interactive ? onPointerMove : undefined}
        onPointerLeave={interactive ? onPointerLeave : undefined}
        onPointerDown={interactive ? onPointerDown : undefined}
        onKeyDown={interactive ? onKeyDown : undefined}
        onFocus={interactive ? onFocus : undefined}
        onBlur={interactive ? onBlur : undefined}
      >
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity="0.38" />
            <stop offset="55%" stopColor={stroke} stopOpacity="0.12" />
            <stop offset="100%" stopColor={stroke} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon fill={`url(#${gid})`} points={geo.areaPoints} />
        <polyline
          fill="none"
          stroke={stroke}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          points={geo.linePoints}
        />
        <circle
          cx={last.x}
          cy={last.y}
          r="2.5"
          fill={stroke}
          vectorEffect="non-scaling-stroke"
          opacity={active ? 0.35 : 1}
        />
        {active ? (
          <g aria-hidden>
            <line
              x1={active.x}
              x2={active.x}
              y1={geo.padY}
              y2={geo.height - geo.padY}
              stroke={stroke}
              strokeWidth="1"
              strokeDasharray="2 2"
              vectorEffect="non-scaling-stroke"
              opacity={0.7}
            />
            <circle
              cx={active.x}
              cy={active.y}
              r="3.5"
              fill={stroke}
              stroke="oklch(1 0 0)"
              strokeWidth="1.25"
              vectorEffect="non-scaling-stroke"
            />
            <rect
              x={tipX - 34}
              y={tipY - 11}
              width={68}
              height={14}
              rx={3}
              fill="oklch(0.22 0.01 260 / 0.92)"
            />
            <text
              x={tipX}
              y={tipY}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="oklch(0.98 0.002 250)"
              fontSize="8"
              fontFamily="ui-monospace, monospace"
            >
              {tipText && tipText.length > 16
                ? `${tipText.slice(0, 15)}…`
                : tipText}
            </text>
          </g>
        ) : null}
      </svg>
      {interactive ? (
        <p className="sr-only" aria-live="polite">
          {tipText ?? "No point selected"}
        </p>
      ) : null}
    </div>
  );
}
