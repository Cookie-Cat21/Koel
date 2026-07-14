"use client";

/**
 * Optional Apache lightweight-charts shell (S1).
 * Enabled only when NEXT_PUBLIC_CHIME_LWC=1 — otherwise unused.
 * Does not load TradingView-owned data; points come from Chime Postgres.
 */
export function OptionalLwcNote({ enabled }: { enabled: boolean }) {
  if (!enabled) return null;
  return (
    <p className="mt-2 text-xs text-muted-foreground" role="status">
      LWC chart flag is on — chart points still come from poller snapshots only
      (browser never scrapes the exchange). Wire lightweight-charts when ready.
    </p>
  );
}
