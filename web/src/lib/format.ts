import { MAX_ISO_INPUT_LENGTH } from "@/lib/api/time";

/** True only for finite number primitives (rejects string/NaN/±Infinity). */
function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

const CTRL_RE = /[\u0000-\u001F\u007F-\u009F]/;

/** Cap fraction digits — hostile / huge values used to throw in toLocaleString. */
export const MAX_FORMAT_FRACTION_DIGITS = 8;

/** Format a number for display; empty when nullish or non-finite. */
export function formatNumber(
  value: number | null | undefined,
  digits = 2,
): string {
  // Guard non-numbers: string prices must not reach toLocaleString via bad JSON.
  if (!isFiniteNumber(value)) return "—";
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
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatTs(iso: string | null | undefined): string {
  // Parity with toIso: reject overlong / control-laden timestamp strings.
  if (typeof iso !== "string" || !iso) return "—";
  const trimmed = iso.trim();
  if (!trimmed || trimmed.length > MAX_ISO_INPUT_LENGTH) return "—";
  if (CTRL_RE.test(trimmed)) return "—";
  const d = new Date(trimmed);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-LK", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Colombo",
  });
}

export function alertTypeLabel(type: string): string {
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
