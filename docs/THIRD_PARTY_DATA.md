# Third-party *market data* checklist (not npm/PyPI)

Runtime open-source packages stay in [`THIRD_PARTY.md`](THIRD_PARTY.md) / [`docs/THIRD_PARTY.md`](THIRD_PARTY.md).  
This file tracks **external market / macro feeds** considered for Signal Board factors.

## Rules (locked)

1. Python adapter only → Postgres → `web/` reads DB (never calls the feed).
2. Feature-flagged + rate-limited + circuit-breaker shared patterns.
3. Log ToS / license / attribution here **before** enabling in prod.
4. No competitor scrape (`csetracker.lk` etc.).
5. Not a Finnhub / TradingView **data spine** ([KOEL_MASTER_PLAN.md](factory/KOEL_MASTER_PLAN.md)).

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

Product roadmap for additive macros (FX / oil / food / tourism / world / news):  
[`docs/factory/MACRO_EXPANSION_MASTER_PLAN.md`](factory/MACRO_EXPANSION_MASTER_PLAN.md).  
Do **not** flip prod flags until the matching intake row below is completed.

## Tier B candidate intake — research log (2026-07-20)

Probe notes only. **Not license clearance.** Complete the full checklist before `*_ENABLED=1`.

### CBSL FX (F-091) — candidate

- [ ] Source: [Daily indicative exchange rates](https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates) · tool `https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates.php` (HTTP 200 in probe) + spreadsheet downloads on same hub
- [ ] ToS / license: official public statistics; confirm redistribution into Postgres + attribution wording
- [ ] Auth: none (HTML/spreadsheet)
- [ ] Rate limit: ≤1 pull / business day after publish; backoff on 5xx
- [ ] Schema: `macro_series` (`source=cbsl_fx`, `series_id=USD_LKR` …)
- [ ] Flag: `CBSL_FX_ENABLED` default `0`
- [ ] Fail-soft: hide FX chips; CSE tape pulse unaffected
- [ ] NFA: “USD/LKR as of …” never “rupee cheap → buy”
- **Note:** Frankfurter/ECB API is fine for USD↔EUR/INR/SGD cross-checks but **does not publish LKR** (confirmed 2026-07-20) — CBSL remains LKR truth.

### EIA oil (F-095) — candidate

- [ ] Source: [EIA Open Data API](https://www.eia.gov/opendata/) — Brent / WTI spot series
- [ ] ToS / license: US government works generally **public domain**; [Copyrights & Reuse](https://www.eia.gov/about/copyrights_reuse.cfm) requires acknowledgment; register free API key; obey API ToS / rate limits
- [ ] Auth: `EIA_API_KEY`
- [ ] Rate limit: polite daily pull; respect EIA throttles
- [ ] Schema: `macro_series` (`source=eia_oil`, `series_id=BRENT_SPOT` / `WTI_SPOT`)
- [ ] Flag: `EIA_OIL_ENABLED` default `0`
- [ ] Fail-soft: hide oil chip
- [ ] NFA: descriptive Δ% only; optional energy-sector bridge chip

### DCS food / CPI (F-093 / food pressure) — candidate

- [ ] Source: [DCS Weekly Retail Prices dashboard](https://www.statistics.gov.lk/DashBoard/Prices/) (HTTP 200) · monthly [CCPI](https://www.statistics.gov.lk/InflationAndPrices/StaticalInformation/MonthlyCCPI) · optional [CBSL Daily Price Report](https://www.cbsl.gov.lk/statistics/economic-indicators/price-report)
- [ ] ToS / license: DCS copyright notice on dashboard (“All Rights Reserved”) — **confirm redistribution** before any scrape/parse; prefer published bulletins/spreadsheets if clearer
- [ ] Auth: none
- [ ] Rate limit: weekly (retail) / monthly (CCPI)
- [ ] Schema: `macro_series` + small staple basket → food pressure score in `macro_snapshots_daily`
- [ ] Flag: `DCS_FOOD_ENABLED` default `0`
- [ ] Fail-soft: hide Food module on `/context`
- [ ] NFA: staples pressure, not “inflation trade”

### SLTDA tourism (F-097) — candidate

- [ ] Source: [Tourist arrivals from all countries](https://www.sltda.gov.lk/en/tourist-arrivals-from-all-countries) Excel/PDF (portal HTTP 200; files listed through 2026-05 in probe)
- [ ] ToS / license: official stats publication; attribute SLTDA; confirm Excel reuse
- [ ] Auth: none (file download)
- [ ] Rate limit: monthly (weekly report optional later)
- [ ] Schema: `macro_series` / tourism monthly table
- [ ] Flag: `SLTDA_TOURISM_ENABLED` default `0`
- [ ] Fail-soft: hide Tourism module
- [ ] NFA: arrivals YoY + Hotels/Travel sector link only
- **Note:** World Bank `ST.INT.ARVL` API responds but recent annual values were **null** in probe — do not use as dash truth.

### World indexes (F-096) — research panel only

- [ ] Source: TBD ToS-clean EOD (avoid brittle bot-gated scrapers; Stooq challenged in probe)
- [ ] ToS / license: treat like Tier D* until cleared; banner “research / delayed”
- [ ] Flag: `WORLD_INDEX_RESEARCH_ENABLED` default `0`
- [ ] Never label as CSE official

### External news / social sentiment — deferred

- [ ] Prefer in-house CSE disclosures/notices + existing Gemini brief flags
- [ ] No full-text scrape of EconomyNext / Daily FT / Ada Derana without written license
- [ ] Link-out / RSS only after per-publisher ToS row
- [ ] Skip CSEPal-style social-feed clone

## Broker / CDS public feeds — decision log (2026-07-18)

Plan: [`docs/experiments/BROKER_PUBLIC_FEEDS_PLAN.md`](experiments/BROKER_PUBLIC_FEEDS_PLAN.md).  
Spike (historical research only): `python3 scripts/experiments/lolc_public_feeds_spike.py` → [`LOLC_PUBLIC_FEEDS_SPIKE.md`](experiments/LOLC_PUBLIC_FEEDS_SPIKE.md).  
**Not holdings** — personal CDS/broker positions remain unavailable via public API.

### LOLC StockLens + dividend calendar — **REJECTED (Tier E)**

- Source (intentional public UI backends, not a leak):  
  `https://www.lolcsecurities.lk/api/stock-screener/` · `…/dividend-calendar/dividends_db.csv`
- ToS / license: **NO-GO for product reuse** —  
  [Terms and Conditions](https://www.lolcsecurities.lk/terms-and-conditions.html) **Use License** allows only a temporary download of materials for **individual and non-business** use, and forbids **commercial use**, **public presentation**, **modify/copy**, and **transfer to another server**. Footer: “All Rights Reserved.”
- Decision (2026-07-18): **Do not ingest into Quiverly Postgres, dash, Telegram, or Signal Board** without a written license / permission from LOLC. No prod flags. Spike script stays research-documentation only.
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
