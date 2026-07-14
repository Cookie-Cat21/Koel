"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { LiveIndicator } from "@/components/live-indicator";

/** Soft-cap refresh interval — never hammer the dash SSR path. */
export const MIN_PRICE_REFRESH_MS = 5_000;
export const DEFAULT_PRICE_REFRESH_MS = 15_000;
export const MAX_PRICE_REFRESH_MS = 120_000;

const STALE_MS = 3 * 60_000;
const DOWN_MS = 15 * 60_000;

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

  useEffect(() => {
    const tick = window.setInterval(() => {
      router.refresh();
      setNow(Date.now());
    }, period);
    const age = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => {
      window.clearInterval(tick);
      window.clearInterval(age);
    };
  }, [period, router]);

  let tone: "ok" | "stale" | "down" = "ok";
  let label = "Refreshing";
  if (typeof lastSnapshotAt === "string" && lastSnapshotAt) {
    const t = Date.parse(lastSnapshotAt);
    if (!Number.isNaN(t)) {
      const ageMs = Math.max(0, now - t);
      const ageSec = Math.floor(ageMs / 1000);
      if (ageMs >= DOWN_MS) {
        tone = "down";
        label =
          ageSec >= 3600
            ? `Stale ${Math.floor(ageSec / 3600)}h`
            : `Stale ${Math.floor(ageSec / 60)}m`;
      } else if (ageMs >= STALE_MS) {
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

  return (
    <span aria-live="polite">
      <LiveIndicator label={label} tone={tone} className="shrink-0" />
    </span>
  );
}
