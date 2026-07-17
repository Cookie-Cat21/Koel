"use client";

import { candleBodyOpen, type DailyBarPoint } from "@/lib/api/daily-bars";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Lightweight SVG candlestick chart (green up / red down).
 * When open is missing, body/color use previous close.
 * Fills its parent when ``fill`` is set — research display only.
 */
export function CandlestickChart({
  bars,
  className,
  forecastPrices,
  showForecast = false,
  fill = false,
  footnote,
}: {
  bars: DailyBarPoint[];
  className?: string;
  forecastPrices?: number[];
  showForecast?: boolean;
  /** Stretch to fill parent flex area instead of fixed aspect cap. */
  fill?: boolean;
  footnote?: string;
}) {
  if (bars.length < 2) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Need at least two bars for a candlestick chart.
      </p>
    );
  }

  const padL = 10;
  const padR = 48;
  const padT = 16;
  const padB = 32;
  const w = 1000;
  const h = 560;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;

  const fc =
    showForecast && forecastPrices
      ? forecastPrices.filter((p) => Number.isFinite(p) && p > 0)
      : [];

  let barMin = Infinity;
  let barMax = -Infinity;
  for (const b of bars) {
    if (b.low < barMin) barMin = b.low;
    if (b.high > barMax) barMax = b.high;
  }
  const barSpan = barMax > barMin ? barMax - barMin : Math.max(Math.abs(barMax) * 0.01, 0.01);
  // Pad candles so they aren't glued to the edge.
  let min = barMin - barSpan * 0.1;
  let max = barMax + barSpan * 0.1;
  // Include forecast in scale only within ±30% of candle span — otherwise
  // a wild model path crushes the candles into a flat strip.
  const fcLo = barMin - barSpan * 0.3;
  const fcHi = barMax + barSpan * 0.3;
  for (const p of fc) {
    if (p < min) min = Math.max(p, fcLo);
    if (p > max) max = Math.min(p, fcHi);
  }
  const span = max > min ? max - min : 1;
  const n = bars.length;
  const totalSlots = n + (fc.length > 0 ? fc.length : 0);
  const slot = plotW / Math.max(1, totalSlots);
  const bodyW = Math.max(2, Math.min(10, slot * 0.62));

  const yFor = (price: number) =>
    padT + (1 - (price - min) / span) * plotH;

  const first = bars[0]!;
  const last = bars[n - 1]!;
  const aria = `Candles from ${first.trade_date} to ${last.trade_date}, close ${formatNumber(last.close)}`;

  const gridYs = [0, 0.25, 0.5, 0.75, 1].map((t) => padT + t * plotH);

  let upN = 0;
  let downN = 0;
  let flatN = 0;

  return (
    <div
      className={cn(
        "flex w-full flex-col",
        fill ? "h-full min-h-0" : "min-h-[320px]",
        className,
      )}
    >
      <svg
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        className={cn("w-full", fill ? "min-h-0 flex-1" : "h-[min(55vh,520px)]")}
        role="img"
        aria-label={aria}
      >
        <rect
          x={0}
          y={0}
          width={w}
          height={h}
          className="fill-muted/25"
          rx={10}
        />
        {gridYs.map((gy) => (
          <line
            key={gy}
            x1={padL}
            x2={w - padR}
            y1={gy}
            y2={gy}
            className="stroke-border/50"
            strokeWidth={1}
          />
        ))}
        {bars.map((b, i) => {
          const bodyOpen = candleBodyOpen(bars, i);
          const cx = padL + slot * i + slot / 2;
          const yH = yFor(b.high);
          const yL = yFor(b.low);
          const yO = yFor(bodyOpen);
          const yC = yFor(b.close);
          const up = b.close > bodyOpen;
          const down = b.close < bodyOpen;
          if (up) upN += 1;
          else if (down) downN += 1;
          else flatN += 1;
          const bodyTop = Math.min(yO, yC);
          const bodyH = Math.max(1.5, Math.abs(yC - yO));
          const stroke = up
            ? "stroke-emerald-600 dark:stroke-emerald-400"
            : down
              ? "stroke-rose-600 dark:stroke-rose-400"
              : "stroke-muted-foreground";
          const fillCls = up
            ? "fill-emerald-500 dark:fill-emerald-400"
            : down
              ? "fill-rose-500 dark:fill-rose-400"
              : "fill-muted-foreground/60";
          return (
            <g key={`${b.trade_date}-${i}`}>
              <line
                x1={cx}
                x2={cx}
                y1={yH}
                y2={yL}
                className={stroke}
                strokeWidth={1.25}
              />
              <rect
                x={cx - bodyW / 2}
                y={bodyTop}
                width={bodyW}
                height={bodyH}
                className={`${fillCls} ${stroke}`}
                strokeWidth={0.5}
              />
            </g>
          );
        })}
        {fc.length > 0 ? (
          <polyline
            fill="none"
            className="stroke-sky-600 dark:stroke-sky-400"
            strokeWidth={2.5}
            strokeDasharray="6 4"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={[
              `${padL + slot * (n - 1) + slot / 2},${yFor(last.close)}`,
              ...fc.map(
                (p, i) =>
                  `${padL + slot * (n + i) + slot / 2},${yFor(p)}`,
              ),
            ].join(" ")}
          />
        ) : null}
        <text
          x={padL}
          y={h - 10}
          className="fill-muted-foreground"
          fontSize={12}
        >
          {first.trade_date}
        </text>
        <text
          x={w - padR}
          y={h - 10}
          textAnchor="end"
          className="fill-muted-foreground"
          fontSize={12}
        >
          {last.trade_date}
        </text>
        <text
          x={w - 8}
          y={padT + 12}
          textAnchor="end"
          className="fill-muted-foreground"
          fontSize={12}
        >
          {formatNumber(max)}
        </text>
        <text
          x={w - 8}
          y={h - padB}
          textAnchor="end"
          className="fill-muted-foreground"
          fontSize={12}
        >
          {formatNumber(min)}
        </text>
      </svg>
      <p className="mt-2 shrink-0 text-xs leading-relaxed text-muted-foreground">
        {footnote ??
          `${n} bars · close ${formatNumber(first.close)} → ${formatNumber(last.close)} · ${upN} up / ${downN} down${flatN ? ` / ${flatN} flat` : ""}${fc.length > 0 ? " · dashed = model forecast" : ""} · research only`}
      </p>
    </div>
  );
}
