"use client";

import { useLayoutEffect, useRef, useState } from "react";

import {
  aggregateBarsForDisplay,
  candleBodyOpen,
  isCloseOnlyBars,
  synthesizePriorCloseCandles,
  type DailyBarPoint,
} from "@/lib/api/daily-bars";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Native SVG hover tooltip text — date + OHLC (+ volume when stored). */
function barTooltip(
  b: DailyBarPoint,
  bodyOpen: number,
  closeCandles: boolean,
): string {
  const vol =
    b.volume != null && Number.isFinite(b.volume)
      ? ` · Vol ${formatNumber(Math.round(b.volume), 0)}`
      : "";
  const ohlc = `${b.trade_date} · O ${formatNumber(b.open ?? bodyOpen)} H ${formatNumber(
    b.high,
  )} L ${formatNumber(b.low)} C ${formatNumber(b.close)}${vol}`;
  return closeCandles ? `${ohlc} · close→close` : ohlc;
}

/**
 * Readable SVG candlestick chart.
 * ``fitWidth`` sizes slots from the container (ResizeObserver) so the plot
 * fills width without scroll and without non-uniform stretch.
 * Dense inputs are aggregated. Missing open → vs prior close.
 */
export function CandlestickChart({
  bars: rawBars,
  className,
  forecastPrices,
  showForecast = false,
  fill = false,
  /** Fit chart to container width (no horizontal scrollbar). */
  fitWidth = false,
  /**
   * Pack candles at a fixed comfortable pitch and center the plot.
   * Use for the hero strip so a short series doesn't stretch card-wide.
   */
  pack = false,
  /**
   * Cap candle pitch when ``fitWidth`` (px). Wider cards otherwise fatten
   * each body — pass ~8–10 for compare / dense strips that must fill the
   * same frame without looking stretched. Unused width is centered.
   */
  maxSlot,
  /** SVG render height in px when not filling a flex parent. */
  chartHeight,
  footnote,
  maxCandles = 72,
  /**
   * ``close`` — CSE index paths (ASPI / S&P SL20) are close-only; synthesize
   * prior-close OHLC candles (not session range). ``auto`` detects
   * close-only series; ``ohlc`` always draws stored candles.
   */
  variant = "auto",
  /**
   * Overview strip: fewer Y ticks, no last-close pill clash, no verbose
   * footnote — charts stay readable in half-width cards.
   */
  minimal = false,
}: {
  bars: DailyBarPoint[];
  className?: string;
  forecastPrices?: number[];
  showForecast?: boolean;
  fill?: boolean;
  fitWidth?: boolean;
  pack?: boolean;
  maxSlot?: number;
  chartHeight?: number;
  /** Pass ``""`` to hide the caption; omit for the default research line. */
  footnote?: string;
  maxCandles?: number;
  variant?: "auto" | "ohlc" | "close";
  minimal?: boolean;
}) {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const [frame, setFrame] = useState({ w: 720, h: chartHeight ?? 280 });

  // useLayoutEffect so viewBox width matches the card before paint — a stale
  // 720px viewBox + preserveAspectRatio="none" was horizontally stretching
  // every candle (and wick) in wide compare cards.
  useLayoutEffect(() => {
    if (!fitWidth) return;
    const el = frameRef.current;
    if (!el) return;
    const apply = (width: number, height: number) => {
      if (width < 2) return;
      const nextH = fill
        ? Math.max(160, Math.floor(height))
        : (chartHeight ?? 280);
      setFrame((prev) => {
        const nextW = Math.floor(width);
        if (prev.w === nextW && prev.h === nextH) return prev;
        return { w: nextW, h: nextH };
      });
    };
    const measure = () => {
      const rect = el.getBoundingClientRect();
      apply(rect.width, rect.height);
    };
    measure();
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const box = entry.borderBoxSize?.[0];
      if (box) {
        apply(box.inlineSize, box.blockSize);
        return;
      }
      apply(entry.contentRect.width, entry.contentRect.height);
    });
    ro.observe(el);
    // Second pass after fonts/layout settle (compare card is often still
    // expanding when daily bars hydrate in).
    const raf = requestAnimationFrame(measure);
    return () => {
      ro.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [fitWidth, fill, chartHeight, rawBars.length]);

  const priceMax = Math.max(...rawBars.map((b) => b.close), 0);
  // CSE index feeds are close-only — synthesize prior-close OHLC so candles
  // have real bodies (open→close) instead of H=L=C sticks or a line fallback.
  const closeCandles =
    variant === "close" ||
    (variant === "auto" && isCloseOnlyBars(rawBars));
  const sourceBars = closeCandles
    ? synthesizePriorCloseCandles(rawBars)
    : rawBars;
  // Scroll mode may keep a dense 1Y series; fit-width always respects
  // maxCandles so the plot can scale into the container without overflow.
  // For close→close indexes, cap density so multi-day aggregates keep
  // readable body height on ASPI-scale ranges.
  const adaptiveMax =
    closeCandles && fitWidth
      ? Math.min(maxCandles, 90)
      : maxCandles >= 200 && !fitWidth
        ? maxCandles
        : priceMax > 0 && priceMax < 2
          ? Math.min(maxCandles, 40)
          : maxCandles;
  const bars = aggregateBarsForDisplay(sourceBars, adaptiveMax);

  if (bars.length < 2) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Need at least two bars for a candlestick chart.
      </p>
    );
  }

  // Pre-count flats — penny CSE names (0.10 tick) are mostly dojis; candles
  // look like noise, so we prefer a step close chart with move markers.
  let preFlat = 0;
  for (let i = 0; i < bars.length; i++) {
    const o = candleBodyOpen(bars, i);
    if (Math.abs(bars[i]!.close - o) < 1e-12) preFlat += 1;
  }
  const lineMode =
    !closeCandles && priceMax < 3 && preFlat / bars.length >= 0.4;

  const padL = fitWidth ? (minimal ? 6 : 8) : 14;
  // ASPI-scale labels need ~56–62px; too-tight padR clips "23,199.57".
  const padR = fitWidth ? (minimal ? 58 : 52) : 56;
  // Tighter chrome so the OHLC band owns the frame (especially hero).
  // minimal keeps extra top pad so the high label isn't clipped by the card.
  const padT = fitWidth ? (minimal ? 16 : 10) : 20;
  const padB = fitWidth ? (minimal ? 24 : 28) : 40;

  const fc =
    showForecast && forecastPrices
      ? forecastPrices.filter((p) => Number.isFinite(p) && p > 0)
      : [];

  const n = bars.length;
  const totalSlots = Math.max(1, n + (fc.length > 0 ? fc.length : 0));

  // pack (hero): fixed pitch, intrinsic centered width.
  // fitWidth+fill (expand): always use the full frame width — short ranges
  // like 1M get wider candles, not empty side gutters.
  const displayH = chartHeight ?? 280;
  const h = fitWidth && !pack ? frame.h : chartHeight ?? (fitWidth ? 280 : 520);
  const MIN_SLOT = 5;
  const PACK_SLOT = 11;
  // When fitWidth divides a wide card by a short series (e.g. 8 intraday
  // ticks), candles become fat blocks. Cap pitch and center instead.
  const MAX_COMFORT_SLOT = 12;
  const frameW = Math.max(padL + padR + 40, frame.w);
  const innerW = frameW - padL - padR;
  const slotCap =
    typeof maxSlot === "number" &&
    Number.isFinite(maxSlot) &&
    maxSlot >= MIN_SLOT
      ? maxSlot
      : null;
  const filledSlot = Math.max(MIN_SLOT, innerW / Math.max(1, totalSlots));
  const autoComfort =
    fitWidth && !pack && slotCap == null && filledSlot > MAX_COMFORT_SLOT;
  // Comfort pitch: fixed candle width (no JS measure). SVG keeps its aspect
  // ratio inside the card so wide viewports cannot fatten/stretch bodies.
  const comfortPitch =
    autoComfort || (slotCap != null && fitWidth && !pack);
  const slot = pack
    ? PACK_SLOT
    : comfortPitch
      ? (slotCap ?? MAX_COMFORT_SLOT)
      : fitWidth
        ? filledSlot
        : 18;
  const usedPlot = totalSlots * slot;
  const contentW = padL + padR + usedPlot;
  const drawPadL = padL;
  const drawPadR = padR;
  // Wider slots → thicker bodies so ranges fill without looking like sparse ticks.
  const bodyRatio = pack || comfortPitch ? 0.72 : fitWidth ? 0.84 : 0.72;
  const bodyW = pack || fitWidth
    ? Math.max(3.5, Math.min(slot * bodyRatio, slot - 0.75))
    : 13;
  const wickW = pack || fitWidth
    ? Math.max(1.25, Math.min(2.75, slot * 0.16))
    : 2;
  const w = pack || comfortPitch ? contentW : fitWidth ? frameW : contentW;
  const plotH = Math.max(40, h - padT - padB);

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
  // Fit/pack charts: small pad so candles fill the plot; scroll mode keeps
  // a bit more air for dense 1Y reads.
  const yPad = fitWidth || pack ? 0.04 : 0.12;
  let min = Math.max(0, barMin - barSpan * yPad);
  let max = barMax + barSpan * yPad;
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
  const aria = closeCandles
    ? `Close-to-close candles from ${first.trade_date} to ${last.trade_date}, close ${formatNumber(last.close)}`
    : `Candles from ${first.trade_date} to ${last.trade_date}, close ${formatNumber(last.close)}`;
  const gridFracs = minimal ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1];
  const gridYs = gridFracs.map((t) => padT + t * plotH);
  const lastCloseY = yFor(last.close);

  // Pre-pass direction counts — mutating during the JSX map breaks React
  // render purity (react-hooks/immutability). Same epsilon per mode.
  let upN = 0;
  let downN = 0;
  let flatN = 0;
  const dirEps = lineMode ? 0 : span * 1e-6;
  for (let i = 0; i < n; i++) {
    const bodyOpen = candleBodyOpen(bars, i);
    const close = bars[i]!.close;
    if (close > bodyOpen + dirEps) upN += 1;
    else if (close < bodyOpen - dirEps) downN += 1;
    else flatN += 1;
  }
  const aggregated = rawBars.length > bars.length;

  return (
    <div
      className={cn(
        "flex w-full flex-col",
        fill ? "h-full min-h-0" : fitWidth ? "min-h-0" : "min-h-[320px]",
        className,
      )}
    >
      <div
        ref={(el) => {
          frameRef.current = el;
          // Pin scroll to most recent candles (scroll mode only).
          if (!el || fitWidth || pack) return;
          requestAnimationFrame(() => {
            el.scrollLeft = Math.max(0, el.scrollWidth - el.clientWidth);
          });
        }}
        className={cn(
          "relative overflow-hidden rounded-xl border border-border/50 bg-gradient-to-b from-muted/25 to-muted/10",
          pack || comfortPitch
            ? "flex w-full max-w-full items-center justify-center overflow-x-hidden"
            : fitWidth
              ? "w-full overflow-x-hidden"
              : "w-full overflow-x-auto overflow-y-hidden",
          fill && !pack && !comfortPitch ? "min-h-0 flex-1" : "",
        )}
        style={
          pack
            ? // Width-first + aspect-ratio: avoids meet() letterboxing that
              // left empty bands above/below the candles in a fixed-height box.
              {
                width: "100%",
                maxWidth: contentW,
                aspectRatio: `${Math.max(1, w)} / ${Math.max(1, h)}`,
                height: "auto",
              }
            : comfortPitch
              ? { height: displayH, width: "100%" }
              : fitWidth && !fill
                ? { height: displayH }
                : undefined
        }
      >
        <svg
          viewBox={`0 0 ${w} ${h}`}
          data-fit={fitWidth ? "1" : "0"}
          data-max-slot={maxSlot ?? ""}
          data-comfort={comfortPitch ? "1" : "0"}
          preserveAspectRatio={
            pack || comfortPitch
              ? "xMidYMid meet"
              : fitWidth
                ? "none"
                : "xMinYMid meet"
          }
          style={
            comfortPitch
              ? {
                  height: "100%",
                  width: "auto",
                  maxWidth: "100%",
                  aspectRatio: `${Math.max(1, w)} / ${Math.max(1, h)}`,
                  display: "block",
                }
              : pack || fitWidth
                ? {
                    width: "100%",
                    height: "100%",
                    display: "block",
                  }
                : {
                    width: w,
                    height: 460,
                    maxWidth: "none",
                    display: "block",
                  }
          }
          className={
            comfortPitch
              ? "max-h-full"
              : pack || fitWidth
                ? "h-full w-full"
                : "max-w-none"
          }
          role="img"
          aria-label={aria}
        >
          {gridYs.map((gy, gi) => {
            // Skip a grid price label that would collide with the last-close tag.
            const labelClash =
              minimal && Math.abs(gy - lastCloseY) < 14;
            return (
              <g key={gy}>
                <line
                  x1={drawPadL}
                  x2={w - drawPadR}
                  y1={gy}
                  y2={gy}
                  className="stroke-border/45"
                  strokeWidth={1}
                />
                {labelClash ? null : (
                  <text
                    x={w - 10}
                    y={
                      gi === 0
                        ? gy + (minimal ? 10 : 0)
                        : gi === gridYs.length - 1
                          ? gy - (minimal ? 2 : 0)
                          : gy
                    }
                    textAnchor="end"
                    dominantBaseline={
                      gi === 0
                        ? minimal
                          ? "middle"
                          : "hanging"
                        : gi === gridYs.length - 1
                          ? "auto"
                          : "middle"
                    }
                    className="fill-muted-foreground"
                    fontSize={minimal ? 11 : 13}
                  >
                    {formatNumber(
                      max - (gi / (gridYs.length - 1)) * span,
                    )}
                  </text>
                )}
              </g>
            );
          })}
          {lineMode ? (
            <>
              <path
                fill="none"
                className="stroke-foreground/70"
                strokeWidth={2.25}
                strokeLinejoin="round"
                strokeLinecap="round"
                d={bars
                  .map((b, i) => {
                    const x = drawPadL + slot * i + slot / 2;
                    const y = yFor(b.close);
                    return i === 0 ? `M ${x} ${y}` : `H ${x} V ${y}`;
                  })
                  .join(" ")}
              />
              {bars.map((b, i) => {
                const bodyOpen = candleBodyOpen(bars, i);
                const cx = drawPadL + slot * i + slot / 2;
                const yC = yFor(b.close);
                const up = b.close > bodyOpen;
                const down = b.close < bodyOpen;
                return (
                  <g key={`${b.trade_date}-${i}`}>
                    <title>{barTooltip(b, bodyOpen, false)}</title>
                    <rect
                      x={cx - slot / 2}
                      y={padT}
                      width={slot}
                      height={plotH}
                      fill="transparent"
                    />
                    {up || down ? (
                      <circle
                        cx={cx}
                        cy={yC}
                        r={3.5}
                        className={
                          up
                            ? "fill-emerald-500 dark:fill-emerald-400"
                            : "fill-rose-500 dark:fill-rose-400"
                        }
                      />
                    ) : null}
                  </g>
                );
              })}
            </>
          ) : (
            bars.map((b, i) => {
              const bodyOpen = candleBodyOpen(bars, i);
              const cx = drawPadL + slot * i + slot / 2;
              const yH = yFor(b.high);
              const yL = yFor(b.low);
              const yO = yFor(bodyOpen);
              const yC = yFor(b.close);
              const eps = span * 1e-6;
              const up = b.close > bodyOpen + eps;
              const down = b.close < bodyOpen - eps;

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

              // Flat / doji (incl. CSE null-open when close ≈ prior close):
              // real high–low wick + thin body — never a fake "+" cross.
              // Index close→close moves are small vs ASPI scale — floor body
              // height so candles stay readable after fit-width packing.
              const naturalH = Math.abs(yC - yO);
              const minBody = closeCandles
                ? Math.max(minimal ? 3.5 : 6, slot * (minimal ? 0.14 : 0.22))
                : 5;
              const bodyH = up || down
                ? Math.max(naturalH, minBody)
                : Math.max(2, slot * 0.08);
              const bodyTop =
                up || down
                  ? Math.min(yO, yC) - (bodyH - naturalH) / 2
                  : yC - bodyH / 2;

              return (
                <g key={`${b.trade_date}-${i}`}>
                  <title>{barTooltip(b, bodyOpen, closeCandles)}</title>
                  <rect
                    x={cx - slot / 2}
                    y={padT}
                    width={slot}
                    height={plotH}
                    fill="transparent"
                  />
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
            })
          )}
          {/* Last-close reference line + axis tag (TradingView convention) */}
          <g aria-hidden>
            <line
              x1={drawPadL}
              x2={w - drawPadR}
              y1={lastCloseY}
              y2={lastCloseY}
              strokeDasharray="3 3"
              strokeWidth={1}
              className={
                last.close > candleBodyOpen(bars, n - 1)
                  ? "stroke-emerald-600/55 dark:stroke-emerald-400/55"
                  : last.close < candleBodyOpen(bars, n - 1)
                    ? "stroke-rose-600/55 dark:stroke-rose-400/55"
                    : "stroke-muted-foreground/45"
              }
            />
            {minimal ? null : (
              <>
                <rect
                  x={w - drawPadR + 2}
                  y={lastCloseY - 10}
                  width={padR - 6}
                  height={20}
                  rx={5}
                  className={
                    last.close > candleBodyOpen(bars, n - 1)
                      ? "fill-emerald-500/15"
                      : last.close < candleBodyOpen(bars, n - 1)
                        ? "fill-rose-500/15"
                        : "fill-muted"
                  }
                />
                <text
                  x={w - 12}
                  y={lastCloseY}
                  textAnchor="end"
                  dominantBaseline="middle"
                  fontSize={13}
                  fontWeight={600}
                  className={
                    last.close > candleBodyOpen(bars, n - 1)
                      ? "fill-emerald-700 dark:fill-emerald-300"
                      : last.close < candleBodyOpen(bars, n - 1)
                        ? "fill-rose-700 dark:fill-rose-300"
                        : "fill-muted-foreground"
                  }
                >
                  {formatNumber(last.close)}
                </text>
              </>
            )}
          </g>
          {fc.length > 0 ? (
            <polyline
              fill="none"
              className="stroke-sky-600 dark:stroke-sky-400"
              strokeWidth={2.5}
              strokeDasharray="6 4"
              strokeLinejoin="round"
              strokeLinecap="round"
              points={[
                `${drawPadL + slot * (n - 1) + slot / 2},${yFor(last.close)}`,
                ...fc.map(
                  (p, i) =>
                    `${drawPadL + slot * (n + i) + slot / 2},${yFor(p)}`,
                ),
              ].join(" ")}
            />
          ) : null}
          <text
            x={drawPadL}
            y={h - (minimal ? 10 : 14)}
            className="fill-muted-foreground"
            fontSize={minimal ? 10 : 13}
          >
            {first.trade_date}
          </text>
          <text
            x={w - drawPadR}
            y={h - (minimal ? 10 : 14)}
            textAnchor="end"
            className="fill-muted-foreground"
            fontSize={minimal ? 10 : 13}
          >
            {last.trade_date}
          </text>
        </svg>
      </div>
      {footnote === "" || (minimal && footnote == null) ? null : (
        <p className="mt-2.5 shrink-0 text-xs leading-relaxed text-muted-foreground">
          {footnote ??
            (closeCandles
              ? `${rawBars.length} daily closes${aggregated ? ` → ${n} candles` : ""} · close→close (CSE has no session OHLC) · ${formatNumber(first.close)} → ${formatNumber(last.close)} · research only`
              : `${rawBars.length} sessions${aggregated ? ` → ${n} ${lineMode ? "points" : "candles"}` : ""}${lineMode ? " · step path (tick-size name)" : ""} · close ${formatNumber(first.close)} → ${formatNumber(last.close)} · ${upN} up / ${downN} down${flatN ? ` / ${flatN} flat` : ""}${fc.length > 0 ? " · dashed = model forecast" : ""} · research only`)}
        </p>
      )}
    </div>
  );
}
