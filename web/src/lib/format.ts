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

/**
 * Compact filing / large-amount labels (e.g. 21.2B) so metric cards do not
 * truncate mid-digit. Below 10 000 keeps full ``formatNumber`` precision.
 */
export function formatCompactNumber(
  value: number | null | undefined,
  digits = 2,
): string {
  if (!isFiniteNumber(value)) return "—";
  if (Math.abs(value) > MAX_FORMAT_ABS_VALUE) return "—";
  const frac =
    typeof digits === "number" &&
    Number.isInteger(digits) &&
    digits >= 0 &&
    digits <= MAX_FORMAT_FRACTION_DIGITS
      ? digits
      : 2;

  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const tiers: { div: number; suffix: string }[] = [
    { div: 1e12, suffix: "T" },
    { div: 1e9, suffix: "B" },
    { div: 1e6, suffix: "M" },
    { div: 1e3, suffix: "K" },
  ];
  for (const tier of tiers) {
    if (abs >= tier.div) {
      const scaled = abs / tier.div;
      return `${sign}${scaled.toLocaleString("en-LK", {
        minimumFractionDigits: 0,
        maximumFractionDigits: frac,
      })}${tier.suffix}`;
    }
  }
  return formatNumber(value, frac);
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
    case "volume_spike":
      return "Volume spike";
    case "volume_up":
      return "Volume up";
    case "volume_down":
      return "Volume down";
    case "crossing_volume":
      return "Crossing volume";
    case "big_print":
      return "Big print";
    case "gap":
      return "Gap";
    case "buy_in":
      return "Buy-in board";
    case "non_compliance":
      return "Non-compliance";
    case "halt":
      return "Market halt";
    case "bid_heavy":
      return "Bid-heavy book";
    case "ask_heavy":
      return "Ask-heavy book";
    case "eps_above":
      return "EPS above";
    case "eps_below":
      return "EPS below";
    case "eps_yoy_above":
      return "EPS YoY above";
    case "eps_yoy_below":
      return "EPS YoY below";
    case "rev_yoy_above":
      return "Revenue YoY above";
    case "rev_yoy_below":
      return "Revenue YoY below";
    case "profit_yoy_above":
      return "Profit YoY above";
    case "profit_yoy_below":
      return "Profit YoY below";
    default:
      // Fail closed — never echo unknown / hostile type strings into the UI.
      return "Unknown";
  }
}

/** Bot-syntax hint for rule rows (parity /help alert lines). */
export function alertTypeBotHint(type: unknown): string {
  if (typeof type !== "string") return "";
  switch (type) {
    case "price_above":
      return "/alert SYMBOL above PRICE";
    case "price_below":
      return "/alert SYMBOL below PRICE";
    case "daily_move":
      return "/alert SYMBOL move PCT";
    case "disclosure":
      return "/alert SYMBOL disclosure";
    case "volume_spike":
      return "/alert SYMBOL volume spike X";
    case "volume_up":
      return "/alert SYMBOL volume up X";
    case "volume_down":
      return "/alert SYMBOL volume down X";
    case "crossing_volume":
      return "/alert SYMBOL crossing X";
    case "big_print":
      return "/alert SYMBOL print SHARES";
    case "gap":
      return "/alert SYMBOL gap PCT";
    case "buy_in":
      return "/alert SYMBOL buyin";
    case "non_compliance":
      return "/alert SYMBOL noncompliance";
    case "halt":
      return "/alert MARKET halt";
    case "bid_heavy":
      return "/alert SYMBOL bidheavy X";
    case "ask_heavy":
      return "/alert SYMBOL askheavy X";
    case "eps_above":
      return "/alert SYMBOL eps above N";
    case "eps_below":
      return "/alert SYMBOL eps below N";
    case "eps_yoy_above":
      return "/alert SYMBOL eps yoy above PCT";
    case "eps_yoy_below":
      return "/alert SYMBOL eps yoy below PCT";
    case "rev_yoy_above":
      return "/alert SYMBOL rev yoy above PCT";
    case "rev_yoy_below":
      return "/alert SYMBOL rev yoy below PCT";
    case "profit_yoy_above":
      return "/alert SYMBOL profit yoy above PCT";
    case "profit_yoy_below":
      return "/alert SYMBOL profit yoy below PCT";
    default:
      return "";
  }
}
