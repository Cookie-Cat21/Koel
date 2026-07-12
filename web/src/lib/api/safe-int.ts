/**
 * Positive SafeInteger parsing without float trunc or bigint precision loss.
 *
 * ``Number("9007199254740993")`` silently becomes ``MAX_SAFE_INTEGER`` —
 * callers that only check ``Number.isSafeInteger`` after ``Number(...)`` can
 * alias the wrong row. Digits-only + ≤15 matches DELETE /alerts/{id}.
 */

/** Digits-only, ≤15 — bigint-safe ids (no sign / exponent / decimals). */
const DIGITS_ID_RE = /^\d{1,15}$/;

/**
 * Parse a positive SafeInteger id from PG number/string/bigint.
 * Rejects floats, scientific notation, oversized digit strings, ≤0.
 */
export function toSafePositiveInt(raw: unknown): number | null {
  if (typeof raw === "bigint") {
    if (raw <= BigInt(0) || raw > BigInt(Number.MAX_SAFE_INTEGER)) return null;
    return Number(raw);
  }
  if (typeof raw === "number") {
    return Number.isSafeInteger(raw) && raw > 0 ? raw : null;
  }
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (!DIGITS_ID_RE.test(trimmed)) return null;
    const n = Number(trimmed);
    return Number.isSafeInteger(n) && n > 0 ? n : null;
  }
  return null;
}

/**
 * Non-negative SafeInteger (attempt counts, etc.). Invalid → ``fallback``.
 * No float truncation (3.9 must not become 3).
 */
export function toNonNegativeSafeInt(raw: unknown, fallback = 0): number {
  if (typeof raw === "bigint") {
    if (raw < BigInt(0) || raw > BigInt(Number.MAX_SAFE_INTEGER)) return fallback;
    return Number(raw);
  }
  if (typeof raw === "number") {
    return Number.isSafeInteger(raw) && raw >= 0 ? raw : fallback;
  }
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (!DIGITS_ID_RE.test(trimmed)) return fallback;
    const n = Number(trimmed);
    return Number.isSafeInteger(n) && n >= 0 ? n : fallback;
  }
  return fallback;
}
