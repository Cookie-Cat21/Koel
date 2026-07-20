"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { LiveIndicator } from "@/components/live-indicator";
import { isMarketSessionOpen } from "@/lib/market-session";

/** Soft-cap refresh interval — never hammer the dash SSR path. */
export const MIN_PRICE_REFRESH_MS = 5_000;
export const DEFAULT_PRICE_REFRESH_MS = 15_000;
export const MAX_PRICE_REFRESH_MS = 120_000;

/** Snapshot age → “stale” chip / overview banner (market open only). */
export const PRICE_STALE_MS = 3 * 60_000;
/** Snapshot age → “down” chip / stronger overview banner. */
export const PRICE_DOWN_MS = 15 * 60_000;

function clampInterval(ms: number): number {
  if (!Number.isFinite(ms)) return DEFAULT_PRICE_REFRESH_MS;
  return Math.min(
    MAX_PRICE_REFRESH_MS,
    Math.max(MIN_PRICE_REFRESH_MS, Math.round(ms)),
  );
}

/**
 * Near-realtime prices: re-fetch Server Components from Postgres on an
 * interval. CSE has no public quote WebSocket — freshness tracks the poller
 * (``POLL_INTERVAL_SECONDS``), not a broker tape.
 */
export function PriceRefresh({
  intervalMs = DEFAULT_PRICE_REFRESH_MS,
  lastSnapshotAt = null,
}: {
  intervalMs?: number;
  /** ISO timestamp of the newest snapshot on this page (for age chip). */
  lastSnapshotAt?: string | null;
}) {
  const router = useRouter();
  const period = clampInterval(intervalMs);
  const [now, setNow] = useState(() => Date.now());
  const [marketOpen, setMarketOpen] = useState(() => isMarketSessionOpen());

  useEffect(() => {
    const tick = window.setInterval(() => {
      router.refresh();
      setNow(Date.now());
      setMarketOpen(isMarketSessionOpen());
    }, period);
    const age = window.setInterval(() => {
      setNow(Date.now());
      setMarketOpen(isMarketSessionOpen());
    }, 1_000);
    return () => {
      window.clearInterval(tick);
      window.clearInterval(age);
    };
  }, [period, router]);

  let tone: "ok" | "stale" | "down" | "closed" = "ok";
  let label = "Refreshing";
  const snapshotAt = lastSnapshotAt;
  if (!marketOpen) {
    // Outside session hours, aged ticks are expected — calm closed tone.
    tone = "closed";
    if (typeof snapshotAt === "string" && snapshotAt) {
      const t = Date.parse(snapshotAt);
      if (!Number.isNaN(t)) {
        const ageSec = Math.floor(Math.max(0, now - t) / 1000);
        label =
          ageSec >= 3600
            ? `Closed · ${Math.floor(ageSec / 3600)}h`
            : ageSec >= 60
              ? `Closed · ${Math.floor(ageSec / 60)}m`
              : "Market closed";
      } else {
        label = "Market closed";
      }
    } else {
      label = "Market closed";
    }
  } else if (typeof snapshotAt === "string" && snapshotAt) {
    const t = Date.parse(snapshotAt);
    if (!Number.isNaN(t)) {
      const ageMs = Math.max(0, now - t);
      const ageSec = Math.floor(ageMs / 1000);
      if (ageMs >= PRICE_DOWN_MS) {
        tone = "down";
        label =
          ageSec >= 3600
            ? `Stale ${Math.floor(ageSec / 3600)}h`
            : `Stale ${Math.floor(ageSec / 60)}m`;
      } else if (ageMs >= PRICE_STALE_MS) {
        tone = "stale";
        label = `Updated ${Math.floor(ageSec / 60)}m ago`;
      } else if (ageSec < 5) {
        tone = "ok";
        label = "Just updated";
      } else {
        tone = "ok";
        label = `Updated ${ageSec}s ago`;
      }
    }
  }

  // Age label uses Date.now() — suppress hydration mismatch vs SSR clock.
  return (
    <span aria-live="polite" suppressHydrationWarning>
      <LiveIndicator label={label} tone={tone} className="shrink-0" />
    </span>
  );
}
