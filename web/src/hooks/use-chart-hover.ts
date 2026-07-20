"use client";

import {
  useCallback,
  useState,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type RefObject,
} from "react";

import {
  nearestIndexAtX,
  type ChartPoint,
} from "@/lib/chart-geometry";

/**
 * Pointer + keyboard hover for 1D SVG series charts.
 * Caller owns ``svgRef`` (avoids returning a ref object from the hook).
 */
export function useChartHover(
  svgRef: RefObject<SVGSVGElement | null>,
  points: ChartPoint[],
  viewBoxWidth: number,
  enabled: boolean,
) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  // Derive display index — no setState-in-effect when disabled.
  const displayIndex = enabled ? activeIndex : null;

  const resolveIndex = useCallback(
    (clientX: number) => {
      const el = svgRef.current;
      if (!el || points.length === 0 || viewBoxWidth <= 0) return null;
      const rect = el.getBoundingClientRect();
      if (rect.width <= 0) return null;
      const x = ((clientX - rect.left) / rect.width) * viewBoxWidth;
      return nearestIndexAtX(points, x);
    },
    [points, svgRef, viewBoxWidth],
  );

  const onPointerMove = useCallback(
    (e: ReactPointerEvent<SVGSVGElement>) => {
      if (!enabled) return;
      const idx = resolveIndex(e.clientX);
      if (idx != null) setActiveIndex(idx);
    },
    [enabled, resolveIndex],
  );

  const onPointerLeave = useCallback(() => {
    if (!enabled) return;
    setActiveIndex(null);
  }, [enabled]);

  const onPointerDown = useCallback(
    (e: ReactPointerEvent<SVGSVGElement>) => {
      if (!enabled) return;
      e.currentTarget.setPointerCapture?.(e.pointerId);
      const idx = resolveIndex(e.clientX);
      if (idx != null) setActiveIndex(idx);
    },
    [enabled, resolveIndex],
  );

  const onKeyDown = useCallback(
    (e: KeyboardEvent<SVGSVGElement>) => {
      if (!enabled || points.length === 0) return;
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        setActiveIndex((prev) => {
          const cur = prev ?? points.length - 1;
          if (e.key === "ArrowLeft") return Math.max(0, cur - 1);
          return Math.min(points.length - 1, cur + 1);
        });
      } else if (e.key === "Home") {
        e.preventDefault();
        setActiveIndex(0);
      } else if (e.key === "End") {
        e.preventDefault();
        setActiveIndex(points.length - 1);
      } else if (e.key === "Escape") {
        setActiveIndex(null);
      }
    },
    [enabled, points.length],
  );

  const onFocus = useCallback(() => {
    if (!enabled || points.length === 0) return;
    setActiveIndex((prev) => (prev == null ? points.length - 1 : prev));
  }, [enabled, points.length]);

  const onBlur = useCallback(() => {
    setActiveIndex(null);
  }, []);

  return {
    activeIndex: displayIndex,
    onPointerMove,
    onPointerLeave,
    onPointerDown,
    onKeyDown,
    onFocus,
    onBlur,
  };
}
