import { MAX_DATE_MS, MAX_ISO_INPUT_LENGTH } from "@/lib/api/time";

/** True only for finite number primitives (rejects string/NaN/±Infinity). */
function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

const CTRL_RE = /[\u0000-\u001F\u007F-\u009F]/;

/** Cap fraction digits — hostile / huge values used to throw in toLocaleString. */
export const MAX_FORMAT_FRACTION_DIGITS = 8;

/**
 * Cap absolute magnitude for display formatters.
 * Hostile finite extremes (e.g. ``1e308``) used to balloon ``toLocaleString`` /
 * ``toFixed`` into multi-hundred-char strings in price/pct UI.
 * CSE quotes never need more than this; fail closed to em dash.
 */
export const MAX_FORMAT_ABS_VALUE = 1e15;

/** Format a number for display; empty when nullish or non-finite. */
export function formatNumber(
  value: number | null | undefined,
  digits = 2,
): string {
  // Guard non-numbers: string prices must not reach toLocaleString via bad JSON.
  if (!isFiniteNumber(value)) return "—";
  // Fail closed — absurd magnitudes balloon locale output.
  if (Math.abs(value) > MAX_FORMAT_ABS_VALUE) return "—";
  // Fail closed — NaN / negative / oversized digits throw RangeError in V8.
  const frac =
    typeof digits === "number" &&
    Number.isInteger(digits) &&
    digits >= 0 &&
    digits <= MAX_FORMAT_FRACTION_DIGITS
      ? digits
      : 2;
  return value.toLocaleString("en-LK", {
    minimumFractionDigits: frac,
    maximumFractionDigits: frac,
  });
}

export function formatPct(value: number | null | undefined): string {
  // Fail closed: string/boolean/NaN/±Infinity must not throw on toFixed.
  if (!isFiniteNumber(value)) return "—";
  // Fail closed — absurd magnitudes balloon toFixed into multi-KB pct labels.
  if (Math.abs(value) > MAX_FORMAT_ABS_VALUE) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatTs(iso: string | null | undefined): string {
  // Parity with toIso: reject overlong / control-laden / out-of-range stamps.
  if (typeof iso !== "string" || !iso) return "—";
  const trimmed = iso.trim();
  if (!trimmed || trimmed.length > MAX_ISO_INPUT_LENGTH) return "—";
  if (CTRL_RE.test(trimmed)) return "—";
  const d = new Date(trimmed);
  const t = d.getTime();
  // Fail closed — NaN / |t|>MAX_DATE_MS used to throw or balloon locale labels
  // (parity safeToIsoString) even when the ISO string itself fit the length cap.
  if (Number.isNaN(t) || Math.abs(t) > MAX_DATE_MS) return "—";
  try {
    return d.toLocaleString("en-LK", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Colombo",
    });
  } catch {
    return "—";
  }
}

export function alertTypeLabel(type: unknown): string {
  // Fail closed — non-strings must not fall through switch oddly.
  if (typeof type !== "string") return "Unknown";
  switch (type) {
    case "price_above":
      return "Above";
    case "price_below":
      return "Below";
    case "daily_move":
      return "Daily move";
    case "disclosure":
      return "Disclosure";
    default:
      // Fail closed — never echo unknown / hostile type strings into the UI.
      return "Unknown";
  }
}
