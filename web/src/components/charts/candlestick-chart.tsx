"use client";

import {
  aggregateBarsForDisplay,
  candleBodyOpen,
  type DailyBarPoint,
} from "@/lib/api/daily-bars";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Readable SVG candlestick chart.
 * Uses a fixed slot width so dense series stay thick (not a barcode).
 * Dense inputs are aggregated. Missing open → vs prior close.
 */
export function CandlestickChart({
  bars: rawBars,
  className,
  forecastPrices,
  showForecast = false,
  fill = false,
  footnote,
  maxCandles = 72,
}: {
  bars: DailyBarPoint[];
  className?: string;
  forecastPrices?: number[];
  showForecast?: boolean;
  fill?: boolean;
  footnote?: string;
  maxCandles?: number;
}) {
  const priceMax = Math.max(...rawBars.map((b) => b.close), 0);
  // Sub-LKR2 names trade on ~0.10 ticks — fewer aggregates = less doji noise.
  const adaptiveMax =
    priceMax > 0 && priceMax < 2
      ? Math.min(maxCandles, 26)
      : priceMax < 5
        ? Math.min(maxCandles, 48)
        : maxCandles;
  const bars = aggregateBarsForDisplay(rawBars, adaptiveMax);

  if (bars.length < 2) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Need at least two bars for a candlestick chart.
      </p>
    );
  }

  const padL = 14;
  const padR = 56;
  const padT = 20;
  const padB = 40;
  const slot = 14; // fixed candle pitch in viewBox units
  const bodyW = 10;
  const wickW = 1.75;

  const fc =
    showForecast && forecastPrices
      ? forecastPrices.filter((p) => Number.isFinite(p) && p > 0)
      : [];

  const n = bars.length;
  const totalSlots = n + (fc.length > 0 ? fc.length : 0);
  const plotW = totalSlots * slot;
  const w = padL + padR + plotW;
  const h = 520;
  const plotH = h - padT - padB;

  let barMin = Infinity;
  let barMax = -Infinity;
  for (const b of bars) {
    if (Number.isFinite(b.low)) barMin = Math.min(barMin, b.low);
    if (Number.isFinite(b.high)) barMax = Math.max(barMax, b.high);
    barMin = Math.min(barMin, b.close);
    barMax = Math.max(barMax, b.close);
    if (b.open != null) {
      barMin = Math.min(barMin, b.open);
      barMax = Math.max(barMax, b.open);
    }
  }
  if (!Number.isFinite(barMin) || !Number.isFinite(barMax)) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Invalid price range for chart.
      </p>
    );
  }

  const barSpan =
    barMax > barMin
      ? barMax - barMin
      : Math.max(Math.abs(barMax) * 0.02, 0.02);
  let min = Math.max(0, barMin - barSpan * 0.12);
  let max = barMax + barSpan * 0.12;
  const fcLo = barMin - barSpan * 0.35;
  const fcHi = barMax + barSpan * 0.35;
  for (const p of fc) {
    if (p < min) min = Math.max(p, Math.max(0, fcLo));
    if (p > max) max = Math.min(p, fcHi);
  }
  const span = max > min ? max - min : 1;

  const yFor = (price: number) =>
    padT + (1 - (price - min) / span) * plotH;

  const first = bars[0]!;
  const last = bars[n - 1]!;
  const aria = `Candles from ${first.trade_date} to ${last.trade_date}, close ${formatNumber(last.close)}`;
  const gridYs = [0, 0.25, 0.5, 0.75, 1].map((t) => padT + t * plotH);

  let upN = 0;
  let downN = 0;
  let flatN = 0;
  const aggregated = rawBars.length > bars.length;

  return (
    <div
      className={cn(
        "flex w-full flex-col",
        fill ? "h-full min-h-0" : "min-h-[320px]",
        className,
      )}
    >
      <div
        className={cn(
          "relative w-full overflow-x-auto overflow-y-hidden rounded-xl border border-border/60 bg-muted/15",
          fill ? "min-h-0 flex-1" : "",
        )}
      >
        <svg
          viewBox={`0 0 ${w} ${h}`}
          preserveAspectRatio="xMidYMid meet"
          className={cn(
            "mx-auto block",
            fill ? "h-full min-h-[400px] w-full" : "h-[min(58vh,540px)] w-full",
          )}
          role="img"
          aria-label={aria}
        >
          {gridYs.map((gy) => (
            <line
              key={gy}
              x1={padL}
              x2={w - padR}
              y1={gy}
              y2={gy}
              className="stroke-border/55"
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
            // Use a small epsilon in price space (helps CSE tick-size flats).
            const eps = span * 1e-6;
            const up = b.close > bodyOpen + eps;
            const down = b.close < bodyOpen - eps;
            if (up) upN += 1;
            else if (down) downN += 1;
            else flatN += 1;

            const stroke = up
              ? "stroke-emerald-700 dark:stroke-emerald-400"
              : down
                ? "stroke-rose-700 dark:stroke-rose-400"
                : "stroke-zinc-500 dark:stroke-zinc-400";
            const fillCls = up
              ? "fill-emerald-500 dark:fill-emerald-400"
              : down
                ? "fill-rose-500 dark:fill-rose-400"
                : "fill-zinc-500 dark:fill-zinc-400";

            // Doji / flat: short tick at close (CSE tick-size days have wide
            // high/low that look like broken spikes if drawn full-length).
            if (!up && !down) {
              const tickH = 4;
              const wickPad = 7;
              return (
                <g key={`${b.trade_date}-${i}`}>
                  <line
                    x1={cx}
                    x2={cx}
                    y1={yC - wickPad}
                    y2={yC + wickPad}
                    className={stroke}
                    strokeWidth={wickW}
                    strokeLinecap="round"
                  />
                  <rect
                    x={cx - bodyW / 2}
                    y={yC - tickH / 2}
                    width={bodyW}
                    height={tickH}
                    rx={1}
                    className={fillCls}
                  />
                </g>
              );
            }

            const naturalH = Math.abs(yC - yO);
            const bodyH = Math.max(naturalH, 5);
            const bodyTop = Math.min(yO, yC) - (bodyH - naturalH) / 2;

            return (
              <g key={`${b.trade_date}-${i}`}>
                <line
                  x1={cx}
                  x2={cx}
                  y1={yH}
                  y2={yL}
                  className={stroke}
                  strokeWidth={wickW}
                  strokeLinecap="round"
                />
                <rect
                  x={cx - bodyW / 2}
                  y={bodyTop}
                  width={bodyW}
                  height={bodyH}
                  rx={1.25}
                  className={fillCls}
                />
              </g>
            );
          })}
          {/* Step close path only when enough real moves (skip penny doji noise) */}
          {flatN / n < 0.45 ? (
            <path
              fill="none"
              className="stroke-foreground/25"
              strokeWidth={1.5}
              strokeLinejoin="round"
              strokeLinecap="round"
              d={bars
                .map((b, i) => {
                  const x = padL + slot * i + slot / 2;
                  const y = yFor(b.close);
                  return i === 0 ? `M ${x} ${y}` : `H ${x} V ${y}`;
                })
                .join(" ")}
            />
          ) : null}
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
            y={h - 14}
            className="fill-muted-foreground"
            fontSize={13}
          >
            {first.trade_date}
          </text>
          <text
            x={w - padR}
            y={h - 14}
            textAnchor="end"
            className="fill-muted-foreground"
            fontSize={13}
          >
            {last.trade_date}
          </text>
          <text
            x={w - 12}
            y={padT + 2}
            textAnchor="end"
            dominantBaseline="hanging"
            className="fill-muted-foreground"
            fontSize={13}
          >
            {formatNumber(max)}
          </text>
          <text
            x={w - 12}
            y={h - padB}
            textAnchor="end"
            className="fill-muted-foreground"
            fontSize={13}
          >
            {formatNumber(min)}
          </text>
        </svg>
      </div>
      <p className="mt-2.5 shrink-0 text-xs leading-relaxed text-muted-foreground">
        {footnote ??
          `${rawBars.length} sessions${aggregated ? ` → ${n} candles` : ""} · close ${formatNumber(first.close)} → ${formatNumber(last.close)} · ${upN} up / ${downN} down${flatN ? ` / ${flatN} flat` : ""}${fc.length > 0 ? " · dashed = model forecast" : ""} · research only`}
      </p>
    </div>
  );
}
