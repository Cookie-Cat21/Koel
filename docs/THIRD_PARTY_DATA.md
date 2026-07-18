# Third-party *market data* checklist (not npm/PyPI)

Runtime open-source packages stay in [`THIRD_PARTY.md`](THIRD_PARTY.md) / [`docs/THIRD_PARTY.md`](THIRD_PARTY.md).  
This file tracks **external market / macro feeds** considered for Signal Board factors.

## Rules (locked)

1. Python adapter only → Postgres → `web/` reads DB (never calls the feed).
2. Feature-flagged + rate-limited + circuit-breaker shared patterns.
3. Log ToS / license / attribution here **before** enabling in prod.
4. No competitor scrape (`csetracker.lk` etc.).
5. Not a Finnhub / TradingView **data spine** ([CHIME_MASTER_PLAN.md](factory/CHIME_MASTER_PLAN.md)).

## Tiers

| Tier | Status | Examples |
|---|---|---|
| A — CSE / in-house | **Primary** | Path bars, tradeSummary, sectors, indexes, disclosures, filing_metrics |
| B — public macro | Candidate later | CBSL policy rate / inflation; ToS-clean USD/LKR; WB/IMF open series |
| B* — broker public boards | **Rejected (ToS)** | LOLC StockLens / dividend CSV — see ban note below |
| C — text | Partial | Filing PDF extract + optional Gemini briefs (existing flags) |
| C* — public PDF stats | Candidate (thin) | CDS INFOLINE monthly only; First Capital research still deferred |
| D — commercial | Deferred | Finnhub, Polygon, Bloomberg, … |
| D* — Yahoo CSE (unofficial) | **Research panel only** | `hybrid_daily_bars` via `yfinance` (`.CM` tickers); flag `HYBRID_BACKFILL_ENABLED` default 0; **not** dash truth; CSE wins on overlap; Yahoo cut on/after `YAHOO_STALE_CUTOFF` (2026-02-18) |
| E — banned | Never | Competitor HTML/APIs; dash→upstream scrapers; broker/CDS **holdings** session scrape; **LOLC StockLens / dividends_db reuse without written license** |

## Adapter intake checklist (copy per source)

- [ ] Source name + official URL  
- [ ] ToS / license allows redistribution into Postgres for product use  
- [ ] Auth model (none / API key) + secret env name  
- [ ] Rate limit / politeness  
- [ ] Schema table(s) + migration id  
- [ ] Feature flag default `0`  
- [ ] Fail-soft behavior when feed down  
- [ ] NFA: factors describe data, never “buy/sell”

**No Tier B+ adapters shipped yet** — Signal Board v0 uses Tier A only.

## Broker / CDS public feeds — decision log (2026-07-18)

Plan: [`docs/experiments/BROKER_PUBLIC_FEEDS_PLAN.md`](experiments/BROKER_PUBLIC_FEEDS_PLAN.md).  
Spike (historical research only): `python3 scripts/experiments/lolc_public_feeds_spike.py` → [`LOLC_PUBLIC_FEEDS_SPIKE.md`](experiments/LOLC_PUBLIC_FEEDS_SPIKE.md).  
**Not holdings** — personal CDS/broker positions remain unavailable via public API.

### LOLC StockLens + dividend calendar — **REJECTED (Tier E)**

- Source (intentional public UI backends, not a leak):  
  `https://www.lolcsecurities.lk/api/stock-screener/` · `…/dividend-calendar/dividends_db.csv`
- ToS / license: **NO-GO for product reuse** —  
  [Terms and Conditions](https://www.lolcsecurities.lk/terms-and-conditions.html) **Use License** allows only a temporary download of materials for **individual and non-business** use, and forbids **commercial use**, **public presentation**, **modify/copy**, and **transfer to another server**. Footer: “All Rights Reserved.”
- Decision (2026-07-18): **Do not ingest into Chime Postgres, dash, Telegram, or Signal Board** without a written license / permission from LOLC. No prod flags. Spike script stays research-documentation only.
- Revisit only if LOLC grants written redistribution rights (then re-run intake checklist from scratch).

### CDS INFOLINE (monthly market plumbing) — still candidate (thin)

- [ ] Source: `https://www.cds.lk/services/depository-operations/publications-downloads/cds-monthly-reports/`
- [ ] ToS / license: public publications; attribute CDS; confirm redistribution of extracted scalars before any adapter
- [ ] Auth: none (PDF download)
- [ ] Rate limit: monthly
- [ ] Schema: `cds_monthly_stats` (proposed) — **not started**
- [ ] Flag: `CDS_INFOLINE_ENABLED` default `0` if ever built
- [ ] Fail-soft: hide Overview strip
- [ ] NFA: aggregate market stats only

### First Capital research PDFs — deferred / not pursued

- [ ] Source: `https://firstcapital.lk/research/`
- [ ] ToS / license: **DEFER** — opinion/ratings; Imperva-brittle; low value vs cse.lk filings
- [ ] No adapter planned unless product asks again
