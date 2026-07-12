/** True only for finite number primitives (rejects string/NaN/±Infinity). */
function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Format a number for display; empty when nullish or non-finite. */
export function formatNumber(
  value: number | null | undefined,
  digits = 2,
): string {
  // Guard non-numbers: string prices must not reach toLocaleString via bad JSON.
  if (!isFiniteNumber(value)) return "—";
  return value.toLocaleString("en-LK", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatPct(value: number | null | undefined): string {
  // Fail closed: string/boolean/NaN/±Infinity must not throw on toFixed.
  if (!isFiniteNumber(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatTs(iso: string | null | undefined): string {
  if (typeof iso !== "string" || !iso) return "—";
  const d = new Date(iso);
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
      return type;
  }
}
