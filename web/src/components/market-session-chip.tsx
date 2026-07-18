"use client";

import { useEffect, useState } from "react";

import { LiveIndicator } from "@/components/live-indicator";
import { getMarketSessionState } from "@/lib/market-session";

/**
 * CSE session chip — clock-based (09:30–14:30 SLT weekdays), same fence as
 * the poller. Not a live CSE ``marketStatus`` probe from the browser.
 */
export function MarketSessionChip({ className }: { className?: string }) {
  const [label, setLabel] = useState<"Market open" | "Market closed">(
    () => getMarketSessionState().label,
  );
  const [open, setOpen] = useState(() => getMarketSessionState().open);

  useEffect(() => {
    const tick = () => {
      const next = getMarketSessionState();
      setLabel(next.label);
      setOpen(next.open);
    };
    tick();
    const id = window.setInterval(tick, 30_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <span aria-live="polite" suppressHydrationWarning>
      <LiveIndicator
        label={label}
        tone={open ? "ok" : "closed"}
        className={className}
      />
    </span>
  );
}
