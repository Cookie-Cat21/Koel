"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { LiveIndicator } from "@/components/live-indicator";
import { toIso } from "@/lib/api/time";
import { isMarketSessionOpen } from "@/lib/market-session";

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

function readSnapshotTs(raw: unknown): string | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const r = raw as Record<string, unknown>;
  const direct =
    toIso(r.ts) ??
    toIso(r.lastSnapshotAt) ??
    toIso(r.last_snapshot_at) ??
    toIso(r.snapshot_at);
  if (direct) return direct;
  if (r.snapshot && typeof r.snapshot === "object" && !Array.isArray(r.snapshot)) {
    return toIso((r.snapshot as { ts?: unknown }).ts);
  }
  return null;
}

function newestSnapshotAt(
  left: string | null | undefined,
  right: string | null | undefined,
): string | null {
  const leftIso = toIso(left);
  const rightIso = toIso(right);
  if (!leftIso) return rightIso;
  if (!rightIso) return leftIso;
  return Date.parse(leftIso) >= Date.parse(rightIso) ? leftIso : rightIso;
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
  const [streamSnapshotAt, setStreamSnapshotAt] = useState<string | null>(null);
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

  useEffect(() => {
    if (typeof window.EventSource === "undefined") return;
    let source: EventSource;
    try {
      source = new window.EventSource("/api/v1/stream/snapshots");
    } catch {
      return;
    }
    const handleSnapshot = (event: Event) => {
      if (!(event instanceof MessageEvent)) return;
      try {
        const data = typeof event.data === "string" ? event.data : "";
        const next = readSnapshotTs(JSON.parse(data));
        if (!next) return;
        setStreamSnapshotAt(next);
        setNow(Date.now());
        router.refresh();
      } catch {
        // Ignore malformed stream events; interval refresh remains active.
      }
    };
    source.addEventListener("snapshot", handleSnapshot);
    source.onmessage = handleSnapshot;
    source.onerror = () => {
      source.close();
    };
    return () => {
      source.removeEventListener("snapshot", handleSnapshot);
      source.close();
    };
  }, [router]);

  let tone: "ok" | "stale" | "down" | "closed" = "ok";
  let label = "Refreshing";
  const snapshotAt = newestSnapshotAt(streamSnapshotAt, lastSnapshotAt);
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

  // Age label uses Date.now() — suppress hydration mismatch vs SSR clock.
  return (
    <span aria-live="polite" suppressHydrationWarning>
      <LiveIndicator label={label} tone={tone} className="shrink-0" />
    </span>
  );
}
