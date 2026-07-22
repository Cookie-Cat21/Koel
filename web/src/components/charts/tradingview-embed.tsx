"use client";

import { useEffect, useId, useRef, useState } from "react";

import {
  toTradingViewSymbol,
  tradingViewSymbolUrl,
} from "@/lib/tradingview-symbol";
import { cn } from "@/lib/utils";

declare global {
  interface Window {
    TradingView?: {
      widget: new (options: Record<string, unknown>) => unknown;
    };
  }
}

const TV_SCRIPT = "https://s3.tradingview.com/tv.js";

function loadTvScript(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.TradingView?.widget) return Promise.resolve();
  const existing = document.querySelector<HTMLScriptElement>(
    `script[src="${TV_SCRIPT}"]`,
  );
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("tv.js")), {
        once: true,
      });
      // Already loaded
      if (window.TradingView?.widget) resolve();
    });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = TV_SCRIPT;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("tv.js load failed"));
    document.head.appendChild(script);
  });
}

/**
 * Optional TradingView Advanced Chart — Layer B for power / TA users.
 * Lazy-loads TV script. Never used as koel’s data spine.
 */
export function TradingViewEmbed({
  symbol,
  className,
}: {
  symbol: string;
  className?: string;
}) {
  const containerId = useId().replace(/:/g, "");
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tvSymbol = toTradingViewSymbol(symbol);
  const tvUrl = tradingViewSymbolUrl(symbol);

  useEffect(() => {
    if (!tvSymbol || !hostRef.current) return;
    let cancelled = false;

    (async () => {
      try {
        await loadTvScript();
        if (cancelled || !window.TradingView?.widget || !hostRef.current) return;
        // Clear prior widget DOM
        hostRef.current.innerHTML = "";
        const mount = document.createElement("div");
        mount.id = `tv_${containerId}`;
        mount.className = "h-full w-full";
        hostRef.current.appendChild(mount);
        // TradingView injects into the container by id.
        new window.TradingView.widget({
          autosize: true,
          symbol: tvSymbol,
          interval: "D",
          timezone: "Asia/Colombo",
          theme: "light",
          style: "1",
          locale: "en",
          enable_publishing: false,
          allow_symbol_change: false,
          hide_side_toolbar: false,
          withdateranges: true,
          details: false,
          hotlist: false,
          calendar: false,
          container_id: mount.id,
        });
        setError(null);
      } catch {
        if (!cancelled) {
          setError(
            "Couldn’t load the TradingView widget. Open the symbol on TradingView instead.",
          );
        }
      }
    })();

    return () => {
      cancelled = true;
      if (hostRef.current) hostRef.current.innerHTML = "";
    };
  }, [tvSymbol, containerId]);

  if (!tvSymbol) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        TradingView chart isn’t available for this symbol.
      </p>
    );
  }

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col gap-2", className)}>
      <p
        className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-950 dark:text-amber-100"
        role="note"
      >
        External TradingView chart for{" "}
        <span className="font-mono">{tvSymbol}</span> — often delayed. koel
        alerts and prices still use koel’s poller data. Not financial advice.
        {tvUrl ? (
          <>
            {" "}
            <a
              href={tvUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2"
            >
              Open full TradingView
            </a>{" "}
            for drawings, indicators, and Pine.
          </>
        ) : null}
      </p>
      {error ? (
        <p className="text-sm text-muted-foreground" role="status">
          {error}{" "}
          {tvUrl ? (
            <a
              href={tvUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2"
            >
              Open on TradingView
            </a>
          ) : null}
        </p>
      ) : (
        <div
          ref={hostRef}
          className="tradingview-widget-container min-h-[420px] w-full flex-1 overflow-hidden rounded-xl border border-border/60"
          data-testid="tradingview-embed"
        />
      )}
    </div>
  );
}
