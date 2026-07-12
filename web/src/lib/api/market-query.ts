/**
 * Shared sanitizers for GET /api/v1/symbols, /api/v1/market/movers, and /market.
 * Keeps q length-bounded, control-char-free, and LIKE-safe (no wildcard injection).
 */

export const MAX_MARKET_Q_LENGTH = 64;
export const MAX_SYMBOLS_OFFSET = 10_000;

/** Coerce Next searchParams value (string | string[] | undefined) to one string. */
export function firstSearchParam(
  value: string | string[] | undefined | null,
): string {
  if (value == null) return "";
  if (Array.isArray(value)) return typeof value[0] === "string" ? value[0] : "";
  return typeof value === "string" ? value : "";
}

/**
 * Normalize browse `q`: trim, drop C0/C1 controls + NUL, cap length.
 * Does not HTML-escape — React text/attrs already escape; this blocks
 * reflected control-char / overlong DoS before SQL or attribute reflection.
 */
export function normalizeMarketQuery(raw: unknown): string {
  const s = firstSearchParam(
    typeof raw === "string" || Array.isArray(raw) ? raw : null,
  )
    .replace(/[\u0000-\u001F\u007F-\u009F]/g, "")
    .trim();
  if (!s) return "";
  return s.length > MAX_MARKET_Q_LENGTH
    ? s.slice(0, MAX_MARKET_Q_LENGTH)
    : s;
}

/**
 * Escape `\`, `%`, `_` for PostgreSQL LIKE … ESCAPE '\'.
 * Callers must use ESCAPE '\\' (or equivalent) in SQL.
 */
export function escapeLikePattern(literal: string): string {
  return literal.replace(/\\/g, "\\\\").replace(/%/g, "\\%").replace(/_/g, "\\_");
}
