/**
 * CSE session clock helpers (Asia/Colombo).
 * Parity with ``chime.poller.is_market_open`` — weekdays 09:30–14:30 SLT.
 * Dashboard-only; does not call cse.lk.
 */

const COLOMBO = "Asia/Colombo";
const OPEN_MINUTES = 9 * 60 + 30;
const CLOSE_MINUTES = 14 * 60 + 30;

const WEEKDAY_TO_MON0: Record<string, number> = {
  Mon: 0,
  Tue: 1,
  Wed: 2,
  Thu: 3,
  Fri: 4,
  Sat: 5,
  Sun: 6,
};

function colomboParts(now: Date): { weekdayMon0: number; minutes: number } | null {
  if (!(now instanceof Date) || Number.isNaN(now.getTime())) return null;
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: COLOMBO,
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(now);
    let weekday: string | null = null;
    let hour: number | null = null;
    let minute: number | null = null;
    for (const p of parts) {
      if (p.type === "weekday") weekday = p.value;
      if (p.type === "hour") hour = Number(p.value);
      if (p.type === "minute") minute = Number(p.value);
    }
    if (weekday == null || hour == null || minute == null) return null;
    if (!Number.isFinite(hour) || !Number.isFinite(minute)) return null;
    const weekdayMon0 = WEEKDAY_TO_MON0[weekday];
    if (weekdayMon0 == null) return null;
    return { weekdayMon0, minutes: hour * 60 + minute };
  } catch {
    return null;
  }
}

/** True during CSE cash-session hours (clock fallback; same fence as the poller). */
export function isMarketSessionOpen(now: Date = new Date()): boolean {
  const parts = colomboParts(now);
  if (!parts) return false;
  if (parts.weekdayMon0 >= 5) return false;
  return parts.minutes >= OPEN_MINUTES && parts.minutes <= CLOSE_MINUTES;
}

export type MarketSessionState = {
  open: boolean;
  /** Short chip label. */
  label: "Market open" | "Market closed";
};

export function getMarketSessionState(
  now: Date = new Date(),
): MarketSessionState {
  const open = isMarketSessionOpen(now);
  return {
    open,
    label: open ? "Market open" : "Market closed",
  };
}
