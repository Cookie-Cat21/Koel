/**
 * Map koel CSE symbols → TradingView ``CSELK:`` ids for the optional embed.
 * TV is never the alert/data spine — display only.
 */

import { normalizeSymbol } from "@/lib/api/symbol";

/** TradingView Colombo exchange prefix (verified 2026 — CSELK:JKH.N0000). */
export const TV_CSE_EXCHANGE = "CSELK";

/**
 * Build ``CSELK:SYMBOL`` for Advanced Chart / deep links.
 * Returns null for MARKET / invalid tickers.
 */
export function toTradingViewSymbol(raw: string | null | undefined): string | null {
  const symbol = normalizeSymbol(raw);
  if (!symbol || symbol === "MARKET") return null;
  return `${TV_CSE_EXCHANGE}:${symbol}`;
}

/** Public TradingView symbol page URL (opens full TA tools). */
export function tradingViewSymbolUrl(raw: string | null | undefined): string | null {
  const tv = toTradingViewSymbol(raw);
  if (!tv) return null;
  // TV public URLs use CSELK-JKH.N0000 (hyphen) in the path.
  const slug = tv.replace(":", "-");
  return `https://www.tradingview.com/symbols/${encodeURIComponent(slug)}/`;
}
