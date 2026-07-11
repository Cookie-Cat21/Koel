/** Format a number for display; empty when nullish. */
export function formatNumber(
  value: number | null | undefined,
  digits = 2,
): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-LK", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
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
