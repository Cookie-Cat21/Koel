/**
 * Honest NAV / P/B / ROE derived from stored equity + price + profit.
 * Null when inputs missing or confidence too low — never invent.
 * Research / NFA.
 */

import { toFiniteNumber } from "@/lib/api/finite-number";

export type EquitySnapshot = {
  equity: number;
  equity_scale: string;
  equity_confidence: string;
  equity_as_of: string | null;
  equity_currency: string;
};

export type FundamentalsLabels = {
  /** Scaled equity (NAV proxy) when confidence medium/high. */
  nav: number | null;
  price_to_book: number | null;
  roe_pct: number | null;
  as_of: string | null;
  currency: string;
};

/** Scale raw extract to LKR units; reject tiny junk. */
export function scaleEquityUnits(
  equity: number | null,
  scale: string | null,
): number | null {
  if (equity == null || !Number.isFinite(equity)) return null;
  const mult =
    scale === "millions" ? 1e6 : scale === "thousands" ? 1e3 : 1;
  const v = equity * mult;
  return Number.isFinite(v) && v >= 10_000 ? v : null;
}

export function computeFundamentals(opts: {
  equity: EquitySnapshot | null;
  lastPrice: number | null;
  /** Shares outstanding unknown — P/B uses market_cap / equity when available. */
  marketCap: number | null;
  profit: number | null;
}): FundamentalsLabels {
  const currency =
    opts.equity?.equity_currency &&
    /^[A-Z]{3,8}$/.test(opts.equity.equity_currency)
      ? opts.equity.equity_currency
      : "LKR";
  const conf = opts.equity?.equity_confidence ?? "none";
  const honest = conf === "medium" || conf === "high";
  const nav = honest
    ? scaleEquityUnits(
        opts.equity?.equity ?? null,
        opts.equity?.equity_scale ?? null,
      )
    : null;

  let price_to_book: number | null = null;
  const mcap = toFiniteNumber(opts.marketCap);
  if (nav != null && nav > 0 && mcap != null && mcap > 0) {
    const pb = mcap / nav;
    price_to_book = Number.isFinite(pb) ? pb : null;
  }

  let roe_pct: number | null = null;
  const profit = toFiniteNumber(opts.profit);
  if (nav != null && nav > 0 && profit != null) {
    const roe = (profit / nav) * 100;
    roe_pct = Number.isFinite(roe) ? roe : null;
  }

  return {
    nav,
    price_to_book,
    roe_pct,
    as_of: opts.equity?.equity_as_of ?? null,
    currency,
  };
}
