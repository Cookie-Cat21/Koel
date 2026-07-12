/**
 * Client-safe finite number coerce (no ``pg`` import).
 *
 * Used by dash API egress and the alert create form. Keep this module free of
 * Node-only deps so ``"use client"`` can import it without pulling Postgres.
 */

/** Cap hostile numeric strings before Number() (CSE quotes never need more). */
export const MAX_FINITE_NUMBER_STRING_LENGTH = 32;

/** Decimal only — reject sci-notation / hex / empty (Number("")===0 footgun). */
const FINITE_DECIMAL_RE = /^-?\d+(\.\d+)?$/;

/**
 * Coerce PG numerics / form strings to finite numbers; NaN/±Infinity → null.
 *
 * Medium: bare Number() on any unknown soft-accepted ""→0, true→1, []→0,
 * and "1e2" sci-notation. Only number primitives or plain decimal strings.
 */
export function toFiniteNumber(value: unknown): number | null {
  if (value == null) return null;
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (
      !trimmed ||
      trimmed.length > MAX_FINITE_NUMBER_STRING_LENGTH ||
      !FINITE_DECIMAL_RE.test(trimmed)
    ) {
      return null;
    }
    const n = Number(trimmed);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}
