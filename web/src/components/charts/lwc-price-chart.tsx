"use client";

import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AreaSeries,
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";

import {
  candleBodyOpen,
  type DailyBarPoint,
} from "@/lib/api/daily-bars";
import type {
  KoelChartMarker,
  KoelChartPriceLine,
} from "@/lib/charts/koel-chart-events";
import {
  computeBollinger,
  computeEma,
  computeRsi,
  computeSma,
  type KoelIndicatorFlags,
} from "@/lib/charts/koel-indicators";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export type ChartSeriesStyle = "candle" | "line" | "area";
export type ChartDrawMode = "none" | "hline" | "trend";

export type KoelUserDrawing =
  | { id: string; kind: "hline"; price: number }
  | {
      id: string;
      kind: "trend";
      t1: string;
      p1: number;
      t2: string;
      p2: number;
    };

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

function newDrawId(): string {
  return `d_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}

/**
 * Interactive koel chart — TradingView-inspired workbench on Postgres bars.
 * Styles, MAs/BB/RSI, drawings, plus koel disclosure/fire overlays.
 */
export function LwcPriceChart({
  bars,
  className,
  forecastPrices,
  showForecast = false,
  showVolume = true,
  markers = [],
  priceLines = [],
  seriesStyle = "candle",
  indicators,
  drawMode = "none",
  drawings = [],
  onDrawingsChange,
}: {
  bars: DailyBarPoint[];
  className?: string;
  forecastPrices?: number[];
  showForecast?: boolean;
  showVolume?: boolean;
  markers?: KoelChartMarker[];
  priceLines?: KoelChartPriceLine[];
  seriesStyle?: ChartSeriesStyle;
  indicators?: KoelIndicatorFlags;
  drawMode?: ChartDrawMode;
  drawings?: KoelUserDrawing[];
  onDrawingsChange?: (next: KoelUserDrawing[]) => void;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const mainRef = useRef<
    | ISeriesApi<"Candlestick">
    | ISeriesApi<"Line">
    | ISeriesApi<"Area">
    | null
  >(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const forecastRef = useRef<ISeriesApi<"Line"> | null>(null);
  const sma20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const sma50Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ema12Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const bbMidRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbUpRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbLoRef = useRef<ISeriesApi<"Line"> | null>(null);
  const rsiRef = useRef<ISeriesApi<"Line"> | null>(null);
  const trendSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const markersApiRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const alertLinesRef = useRef<IPriceLine[]>([]);
  const userHLinesRef = useRef<IPriceLine[]>([]);
  const trendDraftRef = useRef<{ t: string; p: number } | null>(null);
  const barsRef = useRef(bars);
  const drawModeRef = useRef(drawMode);
  const drawingsRef = useRef(drawings);
  const onDrawingsChangeRef = useRef(onDrawingsChange);
  const [hover, setHover] = useState<HoverReadout | null>(null);
  const [ready, setReady] = useState(false);
  const [legendExtras, setLegendExtras] = useState<string>("");

  useEffect(() => {
    barsRef.current = bars;
    drawModeRef.current = drawMode;
    drawingsRef.current = drawings;
    onDrawingsChangeRef.current = onDrawingsChange;
  });

  const ind = useMemo(
    () =>
      indicators ?? {
        sma20: false,
        sma50: false,
        ema12: false,
        bb: false,
        rsi: false,
      },
    [indicators],
  );

  // Recreate chart when style / volume / RSI pane structure changes.
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

    let main:
      | ISeriesApi<"Candlestick">
      | ISeriesApi<"Line">
      | ISeriesApi<"Area">;
    if (seriesStyle === "line") {
      main = chart.addSeries(LineSeries, {
        color: "#0f766e",
        lineWidth: 2,
        lastValueVisible: true,
        priceLineVisible: false,
      });
    } else if (seriesStyle === "area") {
      main = chart.addSeries(AreaSeries, {
        lineColor: "#0f766e",
        topColor: "rgba(15, 118, 110, 0.35)",
        bottomColor: "rgba(15, 118, 110, 0.02)",
        lineWidth: 2,
        lastValueVisible: true,
        priceLineVisible: false,
      });
    } else {
      main = chart.addSeries(CandlestickSeries, {
        upColor: "#059669",
        downColor: "#e11d48",
        borderUpColor: "#059669",
        borderDownColor: "#e11d48",
        wickUpColor: "#059669",
        wickDownColor: "#e11d48",
      });
    }

    let volume: ISeriesApi<"Histogram"> | null = null;
    let nextPane = 1;
    if (showVolume) {
      try {
        volume = chart.addSeries(
          HistogramSeries,
          {
            priceFormat: { type: "volume" },
            priceScaleId: "volume",
          },
          nextPane,
        );
        chart.priceScale("volume", nextPane).applyOptions({
          scaleMargins: { top: 0.15, bottom: 0 },
        });
        nextPane += 1;
      } catch {
        volume = null;
      }
    }

    let rsi: ISeriesApi<"Line"> | null = null;
    if (ind.rsi) {
      try {
        rsi = chart.addSeries(
          LineSeries,
          {
            color: "#a855f7",
            lineWidth: 2,
            priceScaleId: "rsi",
            lastValueVisible: true,
            priceLineVisible: false,
          },
          nextPane,
        );
        chart.priceScale("rsi", nextPane).applyOptions({
          scaleMargins: { top: 0.1, bottom: 0.1 },
        });
      } catch {
        rsi = null;
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

    const mkLine = (color: string, dashed = false) =>
      chart.addSeries(LineSeries, {
        color,
        lineWidth: 1,
        lineStyle: dashed ? LineStyle.Dashed : LineStyle.Solid,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });

    const sma20 = ind.sma20 ? mkLine("#2563eb") : null;
    const sma50 = ind.sma50 ? mkLine("#ea580c") : null;
    const ema12 = ind.ema12 ? mkLine("#0891b2") : null;
    const bbMid = ind.bb ? mkLine("#64748b", true) : null;
    const bbUp = ind.bb ? mkLine("#94a3b8", true) : null;
    const bbLo = ind.bb ? mkLine("#94a3b8", true) : null;

    let markersApi: ISeriesMarkersPluginApi<Time> | null = null;
    try {
      markersApi = createSeriesMarkers(main, []);
    } catch {
      markersApi = null;
    }

    chartRef.current = chart;
    mainRef.current = main;
    volumeRef.current = volume;
    forecastRef.current = forecast;
    sma20Ref.current = sma20;
    sma50Ref.current = sma50;
    ema12Ref.current = ema12;
    bbMidRef.current = bbMid;
    bbUpRef.current = bbUp;
    bbLoRef.current = bbLo;
    rsiRef.current = rsi;
    markersApiRef.current = markersApi;
    // Defer ready flag — avoid sync setState in layout effect body.
    const readyTimer = window.setTimeout(() => setReady(true), 0);

    const onClick = (param: {
      time?: Time;
      point?: { x: number; y: number } | undefined;
    }) => {
      const mode = drawModeRef.current;
      if (mode === "none" || !param.point || !mainRef.current) return;
      const price = mainRef.current.coordinateToPrice(param.point.y);
      if (price == null || !Number.isFinite(price)) return;

      if (mode === "hline") {
        const next: KoelUserDrawing[] = [
          ...drawingsRef.current,
          { id: newDrawId(), kind: "hline", price: Number(price) },
        ];
        onDrawingsChangeRef.current?.(next);
        return;
      }

      if (mode === "trend") {
        const barsNow = barsRef.current;
        let t: string | null = null;
        if (typeof param.time === "string") t = param.time;
        else if (param.time != null) {
          // Snap to nearest bar by coordinate index fallback
          t = barsNow[barsNow.length - 1]?.trade_date ?? null;
        }
        if (!t) {
          // Find nearest bar date from time scale
          const idx = Math.min(
            barsNow.length - 1,
            Math.max(0, Math.round((param.point.x / Math.max(el.clientWidth, 1)) * (barsNow.length - 1))),
          );
          t = barsNow[idx]?.trade_date ?? null;
        }
        if (!t) return;
        const draft = trendDraftRef.current;
        if (!draft) {
          trendDraftRef.current = { t, p: Number(price) };
          return;
        }
        const next: KoelUserDrawing[] = [
          ...drawingsRef.current,
          {
            id: newDrawId(),
            kind: "trend",
            t1: draft.t,
            p1: draft.p,
            t2: t,
            p2: Number(price),
          },
        ];
        trendDraftRef.current = null;
        onDrawingsChangeRef.current?.(next);
      }
    };

    chart.subscribeClick(onClick);

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData || !mainRef.current) {
        setHover(null);
        return;
      }
      const mainSeries = mainRef.current;
      const raw = param.seriesData.get(mainSeries) as
        | {
            open?: number;
            high?: number;
            low?: number;
            close?: number;
            value?: number;
          }
        | undefined;
      if (!raw) {
        setHover(null);
        return;
      }
      const close = raw.close ?? raw.value;
      if (close == null || !Number.isFinite(close)) {
        setHover(null);
        return;
      }
      const open = raw.open ?? close;
      const high = raw.high ?? close;
      const low = raw.low ?? close;
      const volPoint = volumeRef.current
        ? (param.seriesData.get(volumeRef.current) as
            | { value?: number }
            | undefined)
        : undefined;
      setHover({
        time: formatHoverTime(param.time),
        open,
        high,
        low,
        close,
        volume:
          volPoint?.value != null && Number.isFinite(volPoint.value)
            ? volPoint.value
            : null,
      });
    });

    return () => {
      window.clearTimeout(readyTimer);
      chart.unsubscribeClick(onClick);
      for (const line of alertLinesRef.current) {
        try {
          main.removePriceLine(line);
        } catch {
          /* */
        }
      }
      alertLinesRef.current = [];
      for (const line of userHLinesRef.current) {
        try {
          main.removePriceLine(line);
        } catch {
          /* */
        }
      }
      userHLinesRef.current = [];
      trendSeriesRef.current = [];
      markersApiRef.current = null;
      chart.remove();
      chartRef.current = null;
      mainRef.current = null;
      volumeRef.current = null;
      forecastRef.current = null;
      sma20Ref.current = null;
      sma50Ref.current = null;
      ema12Ref.current = null;
      bbMidRef.current = null;
      bbUpRef.current = null;
      bbLoRef.current = null;
      rsiRef.current = null;
      setReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- structural recreate
  }, [
    showVolume,
    seriesStyle,
    ind.sma20,
    ind.sma50,
    ind.ema12,
    ind.bb,
    ind.rsi,
  ]);

  // Bars + indicator series data
  useEffect(() => {
    const main = mainRef.current;
    const chart = chartRef.current;
    if (!main || !chart || bars.length < 2 || !ready) return;

    const closes = bars.map((b) => b.close);
    const n = bars.length;

    if (seriesStyle === "candle") {
      (main as ISeriesApi<"Candlestick">).setData(
        bars.map((b, i) => ({
          time: toChartTime(b.trade_date, i, n),
          open: candleBodyOpen(bars, i),
          high: b.high,
          low: b.low,
          close: b.close,
        })),
      );
    } else {
      (main as ISeriesApi<"Line"> | ISeriesApi<"Area">).setData(
        bars.map((b, i) => ({
          time: toChartTime(b.trade_date, i, n),
          value: b.close,
        })),
      );
    }

    if (volumeRef.current) {
      volumeRef.current.setData(
        bars.map((b, i) => {
          const open = candleBodyOpen(bars, i);
          const up = b.close >= open;
          return {
            time: toChartTime(b.trade_date, i, n),
            value: b.volume ?? 0,
            color: up
              ? "rgba(5, 150, 105, 0.35)"
              : "rgba(225, 29, 72, 0.35)",
          };
        }),
      );
    }

    const applyLine = (
      series: ISeriesApi<"Line"> | null,
      points: { index: number; value: number }[],
    ) => {
      if (!series) return;
      series.setData(
        points.map((p) => ({
          time: toChartTime(bars[p.index]!.trade_date, p.index, n),
          value: p.value,
        })),
      );
    };

    applyLine(sma20Ref.current, computeSma(closes, 20));
    applyLine(sma50Ref.current, computeSma(closes, 50));
    applyLine(ema12Ref.current, computeEma(closes, 12));

    if (ind.bb) {
      const bb = computeBollinger(closes, 20, 2);
      applyLine(
        bbMidRef.current,
        bb.map((b) => ({ index: b.index, value: b.mid })),
      );
      applyLine(
        bbUpRef.current,
        bb.map((b) => ({ index: b.index, value: b.upper })),
      );
      applyLine(
        bbLoRef.current,
        bb.map((b) => ({ index: b.index, value: b.lower })),
      );
    }

    if (rsiRef.current) {
      applyLine(rsiRef.current, computeRsi(closes, 14));
    }

    const forecast = forecastRef.current;
    if (forecast && showForecast && forecastPrices && forecastPrices.length > 0) {
      const fn = Math.min(forecastPrices.length, bars.length);
      const start = bars.length - fn;
      forecast.setData(
        forecastPrices.slice(-fn).map((price, j) => ({
          time: toChartTime(bars[start + j]!.trade_date, start + j, n),
          value: price,
        })),
      );
      forecast.applyOptions({ visible: true });
    } else if (forecast) {
      forecast.setData([]);
      forecast.applyOptions({ visible: false });
    }

    const bits: string[] = [];
    if (ind.sma20) bits.push("SMA20");
    if (ind.sma50) bits.push("SMA50");
    if (ind.ema12) bits.push("EMA12");
    if (ind.bb) bits.push("BB(20,2)");
    if (ind.rsi) bits.push("RSI14");
    setLegendExtras(bits.join(" · "));

    chart.timeScale().fitContent();
  }, [bars, forecastPrices, showForecast, ready, seriesStyle, ind]);

  // Event markers
  useEffect(() => {
    const api = markersApiRef.current;
    if (!api || !ready) return;
    const barSet = new Set(bars.map((b) => b.trade_date));
    const sorted = [...markers]
      .filter((m) => barSet.has(m.time))
      .sort((a, b) => a.time.localeCompare(b.time))
      .map((m) => ({
        time: m.time as Time,
        position: m.position,
        shape: m.shape,
        color: m.color,
        text: m.text,
        size: 1.25 as const,
      }));
    try {
      api.setMarkers(sorted);
    } catch {
      /* */
    }
  }, [markers, bars, ready]);

  // Armed alert lines + user h-lines
  useEffect(() => {
    const main = mainRef.current;
    if (!main || !ready) return;
    for (const line of alertLinesRef.current) {
      try {
        main.removePriceLine(line);
      } catch {
        /* */
      }
    }
    alertLinesRef.current = [];
    for (const pl of priceLines) {
      try {
        alertLinesRef.current.push(
          main.createPriceLine({
            price: pl.price,
            color: pl.color,
            lineWidth: 1,
            lineStyle:
              pl.lineStyle === "dashed" ? LineStyle.Dashed : LineStyle.Solid,
            axisLabelVisible: true,
            title: pl.title,
          }),
        );
      } catch {
        /* */
      }
    }

    for (const line of userHLinesRef.current) {
      try {
        main.removePriceLine(line);
      } catch {
        /* */
      }
    }
    userHLinesRef.current = [];
    for (const d of drawings) {
      if (d.kind !== "hline") continue;
      try {
        userHLinesRef.current.push(
          main.createPriceLine({
            price: d.price,
            color: "#334155",
            lineWidth: 1,
            lineStyle: LineStyle.SparseDotted,
            axisLabelVisible: true,
            title: `H ${formatNumber(d.price)}`,
          }),
        );
      } catch {
        /* */
      }
    }
  }, [priceLines, drawings, ready]);

  // Trend drawings as short line series
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !ready) return;
    for (const s of trendSeriesRef.current) {
      try {
        chart.removeSeries(s);
      } catch {
        /* */
      }
    }
    trendSeriesRef.current = [];
    const barIndex = new Map(bars.map((b, i) => [b.trade_date, i]));
    for (const d of drawings) {
      if (d.kind !== "trend") continue;
      if (!barIndex.has(d.t1) || !barIndex.has(d.t2)) continue;
      try {
        const s = chart.addSeries(LineSeries, {
          color: "#cbd5e1",
          lineWidth: 2,
          lastValueVisible: false,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
        });
        const i1 = barIndex.get(d.t1)!;
        const i2 = barIndex.get(d.t2)!;
        const a = i1 <= i2 ? { t: d.t1, p: d.p1, i: i1 } : { t: d.t2, p: d.p2, i: i2 };
        const b = i1 <= i2 ? { t: d.t2, p: d.p2, i: i2 } : { t: d.t1, p: d.p1, i: i1 };
        s.setData([
          { time: a.t as Time, value: a.p },
          { time: b.t as Time, value: b.p },
        ]);
        trendSeriesRef.current.push(s);
      } catch {
        /* */
      }
    }
  }, [drawings, bars, ready]);

  if (bars.length < 2) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Not enough bars for an interactive chart.
      </p>
    );
  }

  const tip = hover ?? null;
  const hasEvents = markers.length > 0 || priceLines.length > 0;

  return (
    <div
      className={cn("relative flex min-h-0 flex-1 flex-col", className)}
      data-draw-mode={drawMode}
    >
      <div
        className="pointer-events-none absolute top-2 left-2 z-10 max-w-[min(100%,36rem)] rounded-md border border-border/60 bg-background/90 px-2.5 py-1.5 font-mono text-[11px] tabular-nums shadow-sm backdrop-blur-sm"
        aria-live="polite"
      >
        {tip ? (
          <span>
            {tip.time} · O {formatNumber(tip.open)} H {formatNumber(tip.high)} L{" "}
            {formatNumber(tip.low)} C {formatNumber(tip.close)}
            {tip.volume != null && tip.volume > 0
              ? ` · Vol ${formatNumber(Math.round(tip.volume), 0)}`
              : ""}
            {legendExtras ? ` · ${legendExtras}` : ""}
          </span>
        ) : (
          <span className="text-muted-foreground">
            {drawMode === "hline"
              ? "Click chart to place a horizontal line"
              : drawMode === "trend"
                ? "Click twice to place a trend line"
                : "Hover for OHLC · scroll zoom · drag pan"}
            {legendExtras ? ` · ${legendExtras}` : ""}
          </span>
        )}
      </div>
      <div
        ref={hostRef}
        className={cn(
          "min-h-[240px] w-full flex-1",
          drawMode !== "none" && "cursor-crosshair",
        )}
        data-testid="lwc-price-chart"
        role="img"
        aria-label="Interactive koel price chart workbench"
      />
      <p className="mt-1.5 text-[11px] text-muted-foreground">
        koel workbench (Postgres + Lightweight Charts)
        {hasEvents
          ? " · amber = disclosure · violet = Telegram fire · dashed = armed alert"
          : ""}
        {legendExtras ? ` · ${legendExtras}` : ""} — research only, not financial
        advice.
      </p>
    </div>
  );
}
