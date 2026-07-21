"use client";

import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";

import {
  candleBodyOpen,
  type DailyBarPoint,
} from "@/lib/api/daily-bars";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

type HoverReadout = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
};

function toChartTime(tradeDate: string, index: number, total: number): Time {
  if (/^\d{4}-\d{2}-\d{2}$/.test(tradeDate)) {
    return tradeDate;
  }
  // Intraday labels are clock strings — give LWC a monotonic unix scale.
  const base = Math.floor(Date.now() / 1000) - total * 60;
  return (base + index * 60) as UTCTimestamp;
}

function formatHoverTime(time: Time): string {
  if (typeof time === "string") return time;
  if (typeof time === "number") {
    try {
      return new Date(time * 1000).toLocaleString("en-GB", {
        timeZone: "Asia/Colombo",
        hour: "2-digit",
        minute: "2-digit",
        day: "2-digit",
        month: "short",
      });
    } catch {
      return String(time);
    }
  }
  if (time && typeof time === "object" && "year" in time) {
    const t = time as { year: number; month: number; day: number };
    return `${t.year}-${String(t.month).padStart(2, "0")}-${String(t.day).padStart(2, "0")}`;
  }
  return "";
}

/**
 * Interactive koel chart (Lightweight Charts) — crosshair, pan, zoom.
 * Postgres bars only. Not a TradingView terminal.
 */
export function LwcPriceChart({
  bars,
  className,
  forecastPrices,
  showForecast = false,
  showVolume = true,
}: {
  bars: DailyBarPoint[];
  className?: string;
  forecastPrices?: number[];
  showForecast?: boolean;
  showVolume?: boolean;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const forecastRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [hover, setHover] = useState<HoverReadout | null>(null);
  const [ready, setReady] = useState(false);

  useLayoutEffect(() => {
    const el = hostRef.current;
    if (!el || bars.length < 2) return;

    let chart: IChartApi;
    try {
      chart = createChart(el, {
        autoSize: true,
        layout: {
          background: { type: ColorType.Solid, color: "transparent" },
          textColor: "rgba(120, 120, 128, 1)",
          attributionLogo: false,
        },
        grid: {
          vertLines: { color: "rgba(120, 120, 128, 0.12)" },
          horzLines: { color: "rgba(120, 120, 128, 0.12)" },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: { labelBackgroundColor: "rgba(80, 80, 90, 0.9)" },
          horzLine: { labelBackgroundColor: "rgba(80, 80, 90, 0.9)" },
        },
        rightPriceScale: { borderVisible: false },
        timeScale: {
          borderVisible: false,
          rightOffset: 4,
          fixLeftEdge: true,
          fixRightEdge: true,
        },
        handleScroll: { mouseWheel: true, pressedMouseMove: true },
        handleScale: {
          axisPressedMouseMove: true,
          mouseWheel: true,
          pinch: true,
        },
      });
    } catch {
      return;
    }

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#059669",
      downColor: "#e11d48",
      borderUpColor: "#059669",
      borderDownColor: "#e11d48",
      wickUpColor: "#059669",
      wickDownColor: "#e11d48",
    });

    let volume: ISeriesApi<"Histogram"> | null = null;
    if (showVolume) {
      // Pane index 1 — LWC v5 requires paneIndex on priceScale() or the
      // custom id is looked up on pane 0 and throws (takes down the page).
      const volumePane = 1;
      try {
        volume = chart.addSeries(
          HistogramSeries,
          {
            priceFormat: { type: "volume" },
            priceScaleId: "volume",
          },
          volumePane,
        );
        chart.priceScale("volume", volumePane).applyOptions({
          scaleMargins: { top: 0.15, bottom: 0 },
        });
      } catch {
        // Volume pane is optional — keep candles if histogram scale fails.
        volume = null;
      }
    }

    const forecast = chart.addSeries(LineSeries, {
      color: "rgba(14, 165, 233, 0.85)",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });

    chartRef.current = chart;
    candleRef.current = candles;
    volumeRef.current = volume;
    forecastRef.current = forecast;
    setReady(true);

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) {
        setHover(null);
        return;
      }
      const candle = param.seriesData.get(candles) as
        | {
            open?: number;
            high?: number;
            low?: number;
            close?: number;
          }
        | undefined;
      if (
        !candle ||
        candle.open == null ||
        candle.high == null ||
        candle.low == null ||
        candle.close == null
      ) {
        setHover(null);
        return;
      }
      const volPoint = volume
        ? (param.seriesData.get(volume) as { value?: number } | undefined)
        : undefined;
      setHover({
        time: formatHoverTime(param.time),
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        volume:
          volPoint?.value != null && Number.isFinite(volPoint.value)
            ? volPoint.value
            : null,
      });
    });

    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
      forecastRef.current = null;
      setReady(false);
    };
    // Recreate only when volume pane preference changes — data updates below.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional
  }, [showVolume]);

  useEffect(() => {
    const candles = candleRef.current;
    const volume = volumeRef.current;
    const forecast = forecastRef.current;
    const chart = chartRef.current;
    if (!candles || !chart || bars.length < 2) return;

    const candleData = bars.map((b, i) => {
      const open = candleBodyOpen(bars, i);
      return {
        time: toChartTime(b.trade_date, i, bars.length),
        open,
        high: b.high,
        low: b.low,
        close: b.close,
      };
    });
    candles.setData(candleData);

    if (volume) {
      volume.setData(
        bars.map((b, i) => {
          const open = candleBodyOpen(bars, i);
          const up = b.close >= open;
          return {
            time: toChartTime(b.trade_date, i, bars.length),
            value: b.volume ?? 0,
            color: up
              ? "rgba(5, 150, 105, 0.35)"
              : "rgba(225, 29, 72, 0.35)",
          };
        }),
      );
    }

    if (forecast && showForecast && forecastPrices && forecastPrices.length > 0) {
      const n = Math.min(forecastPrices.length, bars.length);
      const start = bars.length - n;
      forecast.setData(
        forecastPrices.slice(-n).map((price, j) => ({
          time: toChartTime(
            bars[start + j]!.trade_date,
            start + j,
            bars.length,
          ),
          value: price,
        })),
      );
      forecast.applyOptions({ visible: true });
    } else if (forecast) {
      forecast.setData([]);
      forecast.applyOptions({ visible: false });
    }

    chart.timeScale().fitContent();
  }, [bars, forecastPrices, showForecast, ready]);

  if (bars.length < 2) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Not enough bars for an interactive chart.
      </p>
    );
  }

  const tip = hover ?? null;

  return (
    <div className={cn("relative flex min-h-0 flex-1 flex-col", className)}>
      <div
        className="pointer-events-none absolute top-2 left-2 z-10 rounded-md border border-border/60 bg-background/90 px-2.5 py-1.5 font-mono text-[11px] tabular-nums shadow-sm backdrop-blur-sm"
        aria-live="polite"
      >
        {tip ? (
          <span>
            {tip.time} · O {formatNumber(tip.open)} H {formatNumber(tip.high)} L{" "}
            {formatNumber(tip.low)} C {formatNumber(tip.close)}
            {tip.volume != null && tip.volume > 0
              ? ` · Vol ${formatNumber(Math.round(tip.volume), 0)}`
              : ""}
          </span>
        ) : (
          <span className="text-muted-foreground">
            Hover for OHLC · scroll to zoom · drag to pan
          </span>
        )}
      </div>
      <div
        ref={hostRef}
        className="min-h-[240px] w-full flex-1"
        data-testid="lwc-price-chart"
        role="img"
        aria-label="Interactive price chart"
      />
      <p className="mt-1.5 text-[11px] text-muted-foreground">
        koel data (Postgres) via Lightweight Charts — research only, not financial
        advice.
      </p>
    </div>
  );
}
