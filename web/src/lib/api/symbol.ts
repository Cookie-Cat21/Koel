/** Same regex as chime.bot.SYMBOL_RE — invalid → 400 invalid_symbol. */
export const SYMBOL_RE = /^[A-Za-z0-9]{1,12}(\.[A-Za-z0-9]{1,8})?$/;

/** Normalize to uppercase; return null if empty or fails SYMBOL_RE. */
export function normalizeSymbol(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const s = raw.trim().toUpperCase();
  if (!s || !SYMBOL_RE.test(s)) return null;
  return s;
}

export const ALERT_TYPES = [
  "price_above",
  "price_below",
  "daily_move",
  "disclosure",
] as const;

export type AlertType = (typeof ALERT_TYPES)[number];

export function isAlertType(value: unknown): value is AlertType {
  return (
    typeof value === "string" &&
    (ALERT_TYPES as readonly string[]).includes(value)
  );
}
