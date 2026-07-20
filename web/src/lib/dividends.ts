/**
 * Dividend calculator helpers — ephemeral estimates from DPS × shares.
 * Not a holdings ledger; not tax advice. Parse hints from CSE disclosure text only.
 */

import { toFiniteNumber } from "@/lib/api/finite-number";

/** Cap shares so hostile form input cannot balloon cash labels. */
export const MAX_DIVIDEND_SHARES = 1_000_000_000;

/** Cap DPS (LKR/share) — CSE cash dividends never need more. */
export const MAX_DIVIDEND_DPS = 1_000_000;

/** Cap absolute cash / yield display magnitudes. */
export const MAX_DIVIDEND_CASH = 1e15;

/** Short UI title — drop Rate/XD/Payment boilerplate from seeded titles. */
export function shortDividendTitle(
  title: string | null | undefined,
  fallback = "Dividend",
): string {
  if (typeof title !== "string" || !title.trim()) return fallback;
  let t = title.trim();
  // Cut at first Rate/XD/Payment clause.
  t = t.split(/\bRate of Dividend\b/i)[0] ?? t;
  t = t.split(/\bXD\s*:/i)[0] ?? t;
  t = t.split(/\bPayment\s*:/i)[0] ?? t;
  t = t.replace(/[·|—–-]+\s*$/g, "").replace(/\s+/g, " ").trim();
  if (!t) return fallback;
  return t.length > 72 ? `${t.slice(0, 71).trimEnd()}…` : t;
}

/** Format YYYY-MM-DD for dash (Asia/Colombo medium date). */
export function formatDividendDate(isoDate: string | null | undefined): string {
  if (typeof isoDate !== "string") return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate.trim());
  if (!m) return "—";
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  if (!y || mo < 1 || mo > 12 || d < 1 || d > 31) return "—";
  try {
    return new Date(Date.UTC(y, mo - 1, d)).toLocaleDateString("en-LK", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    });
  } catch {
    return isoDate;
  }
}

const DIVIDEND_HINT_RE =
  /\bdividends?\b|\bcash\s*div(?:idend)?\b|\binterim\s+div|\bfinal\s+div/i;

const DATES_TBD_RE = /dates?\s+to\s+be\s+notified/i;

/** Rs. 2.00 per share · LKR 1.50 · Rate of Dividend: - Rs. 2.00 */
const DPS_PATTERNS: RegExp[] = [
  /rate\s+of\s+dividend\s*[:.\-\s]*rs\.?\s*([0-9]+(?:\.[0-9]+)?)/i,
  /(?:rs\.?|lkr)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:per\s*share)?/i,
  /([0-9]+(?:\.[0-9]+)?)\s*(?:lkr|rs\.?)\s*per\s*share/i,
];

/** XD: - 12.Feb.2019 · XD 12 Feb 2019 · ex-dividend 12/02/2019 */
const XD_PATTERNS: RegExp[] = [
  /\bxd\s*[:.\-\s]+([0-9]{1,2}[./\-\s][A-Za-z]{3,}[./\-\s][0-9]{2,4})/i,
  /\bxd\s*[:.\-\s]+([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{2,4})/i,
  /\bex[-\s]?dividend\s*(?:date)?\s*[:.\-\s]+([0-9]{1,2}[./\-\s][A-Za-z0-9]{1,}[./\-\s][0-9]{2,4})/i,
];

/** Payment: - 22.Feb.2019 */
const PAY_PATTERNS: RegExp[] = [
  /\bpayment\s*[:.\-\s]+([0-9]{1,2}[./\-\s][A-Za-z]{3,}[./\-\s][0-9]{2,4})/i,
  /\bpayment\s*[:.\-\s]+([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{2,4})/i,
  /\bpayable\s*(?:on|date)?\s*[:.\-\s]+([0-9]{1,2}[./\-\s][A-Za-z0-9]{1,}[./\-\s][0-9]{2,4})/i,
];

export type ParsedDividendHints = {
  dps: number | null;
  xd: string | null;
  payment: string | null;
  dates_tbd: boolean;
};

export type DividendEstimate = {
  cash: number | null;
  yield_pct: number | null;
};

/** True when category/title looks like a CSE cash-dividend disclosure. */
export function isDividendDisclosure(
  category: string | null | undefined,
  title: string | null | undefined,
): boolean {
  const hay = `${category ?? ""} ${title ?? ""}`.trim();
  if (!hay) return false;
  return DIVIDEND_HINT_RE.test(hay);
}

function firstCapture(text: string, patterns: RegExp[]): string | null {
  for (const re of patterns) {
    const m = re.exec(text);
    const raw = m?.[1]?.trim();
    if (raw && raw.length <= 40) return raw.replace(/\s+/g, " ");
  }
  return null;
}

/** Best-effort DPS from announcement title/body/brief text. */
export function parseDpsFromText(text: unknown): number | null {
  if (typeof text !== "string" || !text.trim()) return null;
  // Cap hostile multi-MB disclosure text before regex.
  const sample = text.slice(0, 8_000);
  for (const re of DPS_PATTERNS) {
    const m = re.exec(sample);
    if (!m?.[1]) continue;
    const n = toFiniteNumber(m[1]);
    if (n == null || n <= 0 || n > MAX_DIVIDEND_DPS) continue;
    return n;
  }
  return null;
}

export function parseDividendHints(text: unknown): ParsedDividendHints {
  if (typeof text !== "string" || !text.trim()) {
    return { dps: null, xd: null, payment: null, dates_tbd: false };
  }
  const sample = text.slice(0, 8_000);
  return {
    dps: parseDpsFromText(sample),
    xd: firstCapture(sample, XD_PATTERNS),
    payment: firstCapture(sample, PAY_PATTERNS),
    dates_tbd: DATES_TBD_RE.test(sample),
  };
}

/**
 * Merge hints from title + category + optional brief (prefer first non-null).
 */
export function mergeDividendHints(
  parts: Array<string | null | undefined>,
): ParsedDividendHints {
  let dps: number | null = null;
  let xd: string | null = null;
  let payment: string | null = null;
  let dates_tbd = false;
  for (const part of parts) {
    if (typeof part !== "string" || !part.trim()) continue;
    const h = parseDividendHints(part);
    if (dps == null && h.dps != null) dps = h.dps;
    if (xd == null && h.xd != null) xd = h.xd;
    if (payment == null && h.payment != null) payment = h.payment;
    dates_tbd = dates_tbd || h.dates_tbd;
  }
  return { dps, xd, payment, dates_tbd };
}

/** shares × DPS → expected gross cash (LKR). */
export function estimateDividendCash(
  shares: unknown,
  dps: unknown,
): number | null {
  const s = toFiniteNumber(shares);
  const d = toFiniteNumber(dps);
  if (s == null || d == null) return null;
  if (s <= 0 || d <= 0) return null;
  if (s > MAX_DIVIDEND_SHARES || d > MAX_DIVIDEND_DPS) return null;
  const cash = s * d;
  if (!Number.isFinite(cash) || cash > MAX_DIVIDEND_CASH) return null;
  return cash;
}

/** Trailing / event yield % = DPS ÷ last price × 100. */
export function estimateDividendYieldPct(
  dps: unknown,
  price: unknown,
): number | null {
  const d = toFiniteNumber(dps);
  const p = toFiniteNumber(price);
  if (d == null || p == null) return null;
  if (d <= 0 || p <= 0) return null;
  if (d > MAX_DIVIDEND_DPS) return null;
  const y = (d / p) * 100;
  if (!Number.isFinite(y) || Math.abs(y) > MAX_DIVIDEND_CASH) return null;
  return y;
}

export function estimateDividend(
  shares: unknown,
  dps: unknown,
  price: unknown,
): DividendEstimate {
  return {
    cash: estimateDividendCash(shares, dps),
    yield_pct: estimateDividendYieldPct(dps, price),
  };
}
