"use client";

import { useEffect, useState } from "react";

import { LiveIndicator } from "@/components/live-indicator";
import { getMarketSessionState } from "@/lib/market-session";

/**
 * CSE session chip — clock-based (09:30–14:30 SLT weekdays), same fence as
 * the poller. Not a live CSE ``marketStatus`` probe from the browser.
 */
export function MarketSessionChip({ className }: { className?: string }) {
  // Stable SSR label — clock fence can disagree with the client at the
  // open/close boundary and trip Next DevTools hydration Issues.
  const [label, setLabel] = useState<"Market open" | "Market closed" | "Session">(
    "Session",
  );
  const [open, setOpen] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const tick = () => {
      const next = getMarketSessionState();
      setLabel(next.label);
      setOpen(next.open);
      setReady(true);
    };
    tick();
    const id = window.setInterval(tick, 30_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <span aria-live="polite">
      <LiveIndicator
        label={label}
        tone={!ready ? "closed" : open ? "ok" : "closed"}
        className={className}
      />
    </span>
  );
}
