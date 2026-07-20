import { cn } from "@/lib/utils";

/** Allowlisted breaker states from poller health (`circuits.<endpoint>.state`). */
export const CIRCUIT_TRACKER_STATES = [
  "closed",
  "half_open",
  "open",
  "unknown",
] as const;

export type CircuitTrackerState = (typeof CIRCUIT_TRACKER_STATES)[number];

export type CircuitTrackerItem = {
  /** Endpoint / circuit name (already sanitized by caller). */
  name: string;
  state: CircuitTrackerState;
  failures?: number;
};

/** koel oklch tokens — no purple/indigo defaults (parity AppetiteTracker). */
const STATE_COLOR: Record<CircuitTrackerState, string> = {
  closed: "oklch(0.78 0.10 155)",
  half_open: "oklch(0.84 0.08 70)",
  open: "oklch(0.78 0.09 25)",
  unknown: "oklch(0.86 0.04 250)",
};

const STATE_LABEL: Record<CircuitTrackerState, string> = {
  closed: "Closed (ok)",
  half_open: "Half-open",
  open: "Open",
  unknown: "Unknown",
};

export function normalizeCircuitTrackerState(
  raw: string | null | undefined,
): CircuitTrackerState {
  if (raw === "closed" || raw === "half_open" || raw === "open") return raw;
  return "unknown";
}

/**
 * Tremor Tracker pattern (tracker-03 short) — equal-width circuit segments.
 * Adapted from in-tree AppetiteTracker; no Tremor npm dependency.
 */
export function CircuitTracker({
  items,
  className,
  empty = "No circuit snapshots yet.",
}: {
  items: CircuitTrackerItem[];
  className?: string;
  empty?: string;
}) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        {empty}
      </p>
    );
  }

  const hasUnknown = items.some((i) => i.state === "unknown");
  const legendStates: CircuitTrackerState[] = hasUnknown
    ? ["closed", "half_open", "open", "unknown"]
    : ["closed", "half_open", "open"];

  return (
    <div className={cn("w-full space-y-2.5", className)}>
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          CSE circuits
        </p>
        <p className="font-mono text-[10px] tabular-nums text-muted-foreground">
          {items.length} endpoint{items.length === 1 ? "" : "s"}
        </p>
      </div>
      <ul
        className="flex h-3.5 w-full gap-px sm:h-4"
        aria-label={`Circuit breaker state for ${items.length} CSE endpoints`}
      >
        {items.map((item) => {
          const label = STATE_LABEL[item.state];
          const failHint =
            item.failures != null ? `, ${item.failures} failure(s)` : "";
          const title = `${item.name}: ${label}${failHint}`;
          return (
            <li key={item.name} className="min-w-0 flex-1">
              <span
                title={title}
                className="block h-full w-full rounded-[1.5px]"
                style={{ backgroundColor: STATE_COLOR[item.state] }}
                aria-label={title}
              />
            </li>
          );
        })}
      </ul>
      <ul className="mt-3 divide-y divide-border/60 rounded-xl border border-border">
        {items.map((item) => (
          <li
            key={`row-${item.name}`}
            className="flex flex-wrap items-center gap-3 px-3 py-2 sm:px-4"
          >
            <span
              className="inline-block size-2.5 shrink-0 rounded-[2px]"
              style={{ backgroundColor: STATE_COLOR[item.state] }}
              aria-hidden
            />
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-sm text-foreground">
                {item.name}
              </p>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {STATE_LABEL[item.state]}
                {item.failures != null
                  ? ` · failures ${item.failures}`
                  : ""}
              </p>
            </div>
          </li>
        ))}
      </ul>
      <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        {legendStates.map((s) => (
          <li key={s} className="inline-flex items-center gap-1.5">
            <span
              className="inline-block size-2.5 shrink-0 rounded-[2px]"
              style={{ backgroundColor: STATE_COLOR[s] }}
              aria-hidden
            />
            {STATE_LABEL[s]}
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-muted-foreground">
        Color = breaker state (ops signal, not a tip)
      </p>
    </div>
  );
}
