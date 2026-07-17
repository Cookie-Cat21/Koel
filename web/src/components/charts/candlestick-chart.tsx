"use client";

import type { DailyBarPoint } from "@/lib/api/daily-bars";
import { formatNumber } from "@/lib/format";

/**
 * Lightweight SVG daily candlestick chart (green up / red down).
 * Research display only — not a trading terminal.
 */
export function CandlestickChart({
  bars,
  className,
}: {
  bars: DailyBarPoint[];
  className?: string;
}) {
  if (bars.length < 2) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Need at least two daily bars for a candlestick chart.
      </p>
    );
  }

  const padL = 8;
  const padR = 8;
  const padT = 12;
  const padB = 28;
  const w = 720;
  const h = 320;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;

  let min = Infinity;
  let max = -Infinity;
  for (const b of bars) {
    if (b.low < min) min = b.low;
    if (b.high > max) max = b.high;
  }
  const span = max > min ? max - min : 1;
  const n = bars.length;
  const slot = plotW / n;
  const bodyW = Math.max(1.5, Math.min(8, slot * 0.55));

  const yFor = (price: number) =>
    padT + (1 - (price - min) / span) * plotH;

  const first = bars[0]!;
  const last = bars[n - 1]!;
  const aria = `Daily candles from ${first.trade_date} to ${last.trade_date}, close ${formatNumber(last.close)}`;

  // Grid lines at 25/50/75%
  const gridYs = [0.25, 0.5, 0.75].map((t) => padT + t * plotH);

  return (
    <div className={className}>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-auto w-full max-h-[360px]"
        role="img"
        aria-label={aria}
      >
        <rect
          x={0}
          y={0}
          width={w}
          height={h}
          className="fill-muted/20"
          rx={8}
        />
        {gridYs.map((gy) => (
          <line
            key={gy}
            x1={padL}
            x2={w - padR}
            y1={gy}
            y2={gy}
            className="stroke-border/60"
            strokeWidth={1}
          />
        ))}
        {bars.map((b, i) => {
          const cx = padL + slot * i + slot / 2;
          const yH = yFor(b.high);
          const yL = yFor(b.low);
          const yO = yFor(b.open);
          const yC = yFor(b.close);
          const up = b.close >= b.open;
          const bodyTop = Math.min(yO, yC);
          const bodyH = Math.max(1, Math.abs(yC - yO));
          const stroke = up
            ? "stroke-emerald-600 dark:stroke-emerald-400"
            : "stroke-rose-600 dark:stroke-rose-400";
          const fill = up
            ? "fill-emerald-500/90 dark:fill-emerald-400/90"
            : "fill-rose-500/90 dark:fill-rose-400/90";
          return (
            <g key={b.trade_date}>
              <line
                x1={cx}
                x2={cx}
                y1={yH}
                y2={yL}
                className={stroke}
                strokeWidth={1}
              />
              <rect
                x={cx - bodyW / 2}
                y={bodyTop}
                width={bodyW}
                height={bodyH}
                className={`${fill} ${stroke}`}
                strokeWidth={0.5}
              />
            </g>
          );
        })}
        <text
          x={padL}
          y={h - 10}
          className="fill-muted-foreground"
          fontSize={10}
        >
          {first.trade_date}
        </text>
        <text
          x={w - padR}
          y={h - 10}
          textAnchor="end"
          className="fill-muted-foreground"
          fontSize={10}
        >
          {last.trade_date}
        </text>
        <text
          x={w - padR}
          y={padT + 10}
          textAnchor="end"
          className="fill-muted-foreground"
          fontSize={10}
        >
          {formatNumber(max)}
        </text>
        <text
          x={w - padR}
          y={h - padB}
          textAnchor="end"
          className="fill-muted-foreground"
          fontSize={10}
        >
          {formatNumber(min)}
        </text>
      </svg>
      <p className="mt-2 text-xs text-muted-foreground">
        {n} sessions · close {formatNumber(first.close)} →{" "}
        {formatNumber(last.close)} · green up / red down · research only
      </p>
    </div>
  );
}
