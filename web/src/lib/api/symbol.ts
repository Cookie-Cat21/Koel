/** Same regex as chime.bot.SYMBOL_RE — invalid → 400 invalid_symbol. */
export const SYMBOL_RE = /^[A-Za-z0-9]{1,12}(\.[A-Za-z0-9]{1,8})?$/;

/**
 * Decode a path/query segment. Malformed ``%`` sequences throw ``URIError``
 * from ``decodeURIComponent`` — fail closed to ``null`` so API routes return
 * 400 instead of an unhandled 500.
 */
export function safeDecodeURIComponent(raw: unknown): string | null {
  // Fail closed — non-strings used to coerce via ToString into junk paths.
  if (typeof raw !== "string") return null;
  try {
    return decodeURIComponent(raw);
  } catch {
    return null;
  }
}

/** Normalize to uppercase; return null if empty or fails SYMBOL_RE. */
export function normalizeSymbol(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const s = raw.trim().toUpperCase();
  if (!s || !SYMBOL_RE.test(s)) return null;
  return s;
}

/**
 * Decode then normalize a dynamic ``[symbol]`` path param.
 * Malformed percent-encoding → null (same as invalid symbol).
 */
export function normalizeSymbolParam(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const decoded = safeDecodeURIComponent(raw);
  if (decoded == null) return null;
  return normalizeSymbol(decoded);
}

/** Full bot parity — every AlertType in chime.domain. */
export const ALERT_TYPES = [
  "price_above",
  "price_below",
  "daily_move",
  "disclosure",
  "volume_spike",
  "volume_up",
  "volume_down",
  "crossing_volume",
  "big_print",
  "gap",
  "buy_in",
  "non_compliance",
  "halt",
  "bid_heavy",
  "ask_heavy",
  "eps_above",
  "eps_below",
  "eps_yoy_above",
  "eps_yoy_below",
  "rev_yoy_above",
  "rev_yoy_below",
  "profit_yoy_above",
  "profit_yoy_below",
  "appetite_band",
  "foreign_flow",
  "book_pressure",
  "usdlkr_move",
  "oil_move",
] as const;

/** Alert types that require a positive numeric threshold (parity Python). */
export const THRESHOLD_ALERT_TYPES = [
  "price_above",
  "price_below",
  "daily_move",
  "volume_spike",
  "volume_up",
  "volume_down",
  "crossing_volume",
  "big_print",
  "gap",
  "bid_heavy",
  "ask_heavy",
  "eps_above",
  "eps_below",
  "eps_yoy_above",
  "eps_yoy_below",
  "rev_yoy_above",
  "rev_yoy_below",
  "profit_yoy_above",
  "profit_yoy_below",
  "appetite_band",
  "foreign_flow",
  "book_pressure",
  "usdlkr_move",
  "oil_move",
] as const;

/** Notice-style alerts with no threshold (bid/ask need thresholds — not here). */
export const NOTICE_ALERT_TYPES = [
  "disclosure",
  "buy_in",
  "non_compliance",
  "halt",
] as const;

/** Filing-metrics / YoY types — feature-flagged at fire time. */
export const FILING_METRICS_ALERT_TYPES = [
  "eps_above",
  "eps_below",
  "eps_yoy_above",
  "eps_yoy_below",
  "rev_yoy_above",
  "rev_yoy_below",
  "profit_yoy_above",
  "profit_yoy_below",
] as const;

export type AlertType = (typeof ALERT_TYPES)[number];

export function isAlertType(value: unknown): value is AlertType {
  return (
    typeof value === "string" &&
    (ALERT_TYPES as readonly string[]).includes(value)
  );
}

export function isThresholdAlertType(value: unknown): boolean {
  return (
    typeof value === "string" &&
    (THRESHOLD_ALERT_TYPES as readonly string[]).includes(value)
  );
}

export function isFilingMetricsAlertType(value: unknown): boolean {
  return (
    typeof value === "string" &&
    (FILING_METRICS_ALERT_TYPES as readonly string[]).includes(value)
  );
}
