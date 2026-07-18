# Plan: Broker / CDS public feeds (not holdings)

**Date:** 2026-07-18  
**Status:** research complete · **LOLC rejected (ToS)** · no adapters shipped  
**Fence:** Dash density + Telegram alerts + Signal Board factors. No portfolio sync, no buy/sell language, no competitor scrape.

**Spike (historical only — do not productize LOLC):**  
`python3 scripts/experiments/lolc_public_feeds_spike.py` → [`LOLC_PUBLIC_FEEDS_SPIKE.md`](./LOLC_PUBLIC_FEEDS_SPIKE.md)

Related: [`docs/THIRD_PARTY_DATA.md`](../THIRD_PARTY_DATA.md) · [`docs/factory/workstreams/FACTOR_INDEX.md`](../factory/workstreams/FACTOR_INDEX.md) (F-086) · [`docs/factory/CHIME_MASTER_PLAN.md`](../factory/CHIME_MASTER_PLAN.md) (P1 / P1b)

---

## 1. Verdict

Personal holdings remain unreachable via broker/CDS APIs.

**LOLC StockLens + dividend CSV:** technically rich and intentionally public as website tools, but LOLC’s published **Use License** forbids commercial use, public presentation, copying, and transferring materials to another server. **Operator decision 2026-07-18: do not use in Chime** without written permission. Recorded as Tier E in `THIRD_PARTY_DATA.md`.

| Priority | Source | Ship? | Why |
|---|---|---|---|
| — | LOLC StockLens JSON | **No (ToS)** | Would be useful fundamentals board — blocked by site license |
| — | LOLC dividend CSV | **No (ToS)** | Would enable XD alerts — blocked by site license |
| **P1** | CDS INFOLINE monthly PDFs | **Maybe later (thin)** | Domestic/foreign holding value series for Overview — separate ToS check |
| — | First Capital research PDFs | **No / defer** | Imperva-brittle; opinion layer; low value vs cse.lk |

---

## 2. What we probed (2026-07-18)

### 2.1 LOLC StockLens — `GET https://www.lolcsecurities.lk/api/stock-screener/`

| Field | Observation |
|---|---|
| Auth | None |
| Shape | `{ last_modified, data: [...] }` JSON |
| Coverage | **302** symbols, **20** sectors |
| Freshness | `last_modified` observed `2026-07-17 11:24:13` (daily-ish) |
| Empty rates | Near-complete; ROE empty on ~12/302 |
| Keys | `Company Tiker`, name, sector, price, mcap, **Foreign Holding%**, 4QT earnings, PE, sector PE, PBV, sector PBV, DY%, DPS, EPS 4QT, NAV, ROE |

**Signal vs cse.lk:** `companyInfoSummery.foreignHoldings` is often null; StockLens has FH% for all 302 (median ~1%, p90 ~37%). Sector-relative PE/PBV is not in Chime today.

**Parse notes:** ticker key is misspelled `Company Tiker`; numerics arrive as strings with `,` and `%` — normalize in adapter.

### 2.2 LOLC dividend calendar — `GET …/dividend-calendar/dividends_db.csv`

| Field | Observation |
|---|---|
| Auth | None |
| Shape | CSV (~2331 rows, 267 symbols) |
| Columns | `D_ANN`, `D_XD`, `D_PAY`, `CODE`, `DPS`, `INTERIM`, `FY`, … |
| History | XD from **2015-12** → forward dates into **2026-08** |
| Near-term | On probe day, **14** upcoming XD rows (e.g. VLL 2026-07-20, AAF 2026-07-24) |

Better machine feed than parsing CSE announcement HTML for “dividend going XD soon.”

### 2.3 CDS INFOLINE — monthly PDFs on cds.lk

| Field | Observation |
|---|---|
| Auth | None (public downloads) |
| Cadence | Monthly (~6pp PDF) |
| Useful series | New CDS accounts; equity trades; **domestic vs foreign holding qty + value**; foreign company/individual splits |
| Example | April 2026: foreign equity value ~LKR 1.37T vs domestic ~6.69T |

Good for an Overview “market plumbing” strip — not for per-symbol alerts.

### 2.4 First Capital research PDFs

| Field | Observation |
|---|---|
| Auth | No login for some PDFs when reachable |
| Access | Site often Imperva-challenges bare fetchers; WP JSON blocked |
| Content | Earnings updates, BUY/MAINTAIN, fair values / strategy notes |
| Fit | Optional NFA research layer only — **never** tip language in Telegram |

Defer until LOLC + CDS land; treat as opportunistic PDF watcher if ToS OK.

### 2.5 Explicit non-sources

- ATrad / `atsweb` unauthenticated JSON — login wall only  
- StockGPT / AlmasONE / FinView — gated products  
- Broker WhatsApp morning notes — unstructured  
- Personal CDS/broker holdings — still no retail API  

---

## 3. Product opportunities (fence-legal)

### A. Symbol fundamentals strip (dash)

On `/symbols/[symbol]`, show PE, PBV, DY, EPS, NAV, ROE, foreign holding %, with **source + as-of** and NFA.

- Complements existing filing_metrics (event extracts) with a **board-level** snapshot.
- Prices on this feed are secondary — **cse.lk / Chime snapshots remain truth** for last price.

### B. Signal Board factors (unlock F-086 + new IDs)

| Factor | Hypothesis | Input |
|---|---|---|
| **F-086** (OPEN today) | Foreign holding % is informative | StockLens `Foreign Holding%` (fallback if companyInfo null) |
| **F-xxx** (propose) | Cheap vs sector PE | `PE / Sector PE` |
| **F-xxx** (propose) | Cheap vs sector PBV | `PBV / Sector PBV` |
| **F-xxx** (propose) | Dividend yield level | `DY (%)` |
| **F-xxx** (propose) | Δ foreign holding (7d) | snapshot history of FH% |

All reasons must stay descriptive (“foreign holding 37%”, “PE below sector median”) — never “buy/sell.”

### C. Dividend / XD Telegram + dash alerts (cherry)

New alert type (name TBD): e.g. `xd_soon` / `dividend_xd`

| Rule | Behavior |
|---|---|
| `/alert SYMBOL xd DAYS` | Fire once when `D_XD` is within N calendar days and not yet fired for that `(rule, D_XD)` |
| Watchlist digest | Optional daily “XD this week on your watchlist” |
| Dash | Calendar strip on Overview / symbol event timeline |

Dedupe key: `(rule_id, code, d_xd)` or global watchlist digest key per day.

### D. Market-health widget (Overview)

Monthly CDS series: new accounts, domestic/foreign holding value, MoM %.  
One KPI strip — not a trading terminal.

---

## 4. Risks & gates

| Risk | Mitigation |
|---|---|
| **LOLC copyright / ToS** (“All Rights Reserved”) | **Hard gate before prod.** Prefer written OK or clear public-data terms. Until then: flag default `0`, research-only, attribute “Source: LOLC Securities StockLens / Dividend Calendar”. Do not republish full board dumps. |
| Feed disappears / shape drift | Adapter + probe CI fingerprint; fail-soft; CSE remains price spine |
| Stale fundamentals marked as live | Persist `source_as_of` / `last_modified`; UI shows as-of |
| NFA / tip risk (research PDFs, “cheap PE”) | Descriptive factors only; no rating→push tips; FC PDFs deferred |
| Double price sources confuse users | Never prefer LOLC price over Chime snapshots |
| Rate / politeness | ≤1 StockLens pull / 6h; ≤1 dividend CSV / 12h; CDS PDF monthly |

Log intake checklist rows in `THIRD_PARTY_DATA.md` before any flag flip.

---

## 5. Phased build plan

### Phase 0 — Legal + spike (docs / throwaway script only)

1. Capture LOLC T&Cs + risk disclosure; decide **OK / ask / research-only**.  
2. Spike script: pull StockLens + CSV → normalize → print coverage report (no Postgres).  
3. Confirm ticker parity vs `stocks.symbol` (`.N0000` / `.X0000` / prefs).  
4. Update `THIRD_PARTY_DATA.md` candidate rows (this PR).

**Exit:** Go / no-go on redistribution; sample fixture under `docs/sample_responses/` (truncated).

### Phase 1 — Fundamentals ingest (flag off)

| Piece | Detail |
|---|---|
| Flag | `LOLC_FUNDAMENTALS_ENABLED=0` |
| Adapter | `chime/adapters/lolc_stocklens.py` — GET JSON, normalize numbers, map ticker |
| Tables | `fundamentals_snapshots (symbol, as_of, pe, sector_pe, pbv, sector_pbv, dy, dps, eps_4qt, nav, roe, foreign_holding_pct, mcap_mn, source, raw_hash)` |
| Job | `python3 -m chime fundamentals-pull` (cron / poller idle leg) |
| API | Extend `GET /api/v1/symbols/[symbol]/metrics` with optional `fundamentals` block |
| UI | Symbol KPI strip; attribution footer |
| Signals | Wire **F-086** when coverage ≥ threshold |

**Exit:** Flag-off green tests; one forced pull writes rows; dash shows as-of when flag on in staging.

### Phase 2 — Dividend calendar + XD alerts

| Piece | Detail |
|---|---|
| Flag | `LOLC_DIVIDENDS_ENABLED=0` |
| Adapter | `chime/adapters/lolc_dividends.py` |
| Tables | `dividend_events (symbol, d_ann, d_xd, d_pay, dps, interim, fy, UNIQUE…)` |
| Alert type | `xd_soon` (threshold = days ahead) — bot parse + dash create |
| Rules | Evaluate once/day (not every price tick); claim/dedupe like disclosures |
| UI | Symbol event timeline + optional Overview “XD this week” |

**Exit:** Synthetic fixture fires once; no spam on re-pull; NFA line on messages.

### Phase 3 — CDS INFOLINE (thin)

| Piece | Detail |
|---|---|
| Flag | `CDS_INFOLINE_ENABLED=0` |
| Ingest | Discover latest PDF URL from monthly-reports page → extract key scalars (manual schema first) |
| Table | `cds_monthly_stats (month, new_accounts, equity_trades, domestic_holding_value, foreign_holding_value, …)` |
| UI | Overview KPI strip only |

**Exit:** Latest month row present; fail-soft if PDF layout shifts.

### Phase 4 — First Capital research (optional)

- Only after Phases 1–2 stable and legal review of redistributing ratings text.  
- Store `{symbol?, title, url, published_at, rating?, fair_value?}` as **research_notes**.  
- Dash: link-out list; **no** Telegram tip blasts.  
- Kill if Imperva makes polite fetch unreliable.

---

## 6. Suggested schema (Phase 1–2 sketch)

```sql
-- migration TBD; flag-gated writers only
CREATE TABLE fundamentals_snapshots (
  id              bigserial PRIMARY KEY,
  symbol          text NOT NULL REFERENCES stocks(symbol),
  as_of           timestamptz NOT NULL,
  source          text NOT NULL DEFAULT 'lolc_stocklens',
  pe              double precision,
  sector_pe       double precision,
  pbv             double precision,
  sector_pbv      double precision,
  dy_pct          double precision,
  dps             double precision,
  eps_4qt         double precision,
  nav             double precision,
  roe_pct         double precision,
  foreign_holding_pct double precision,
  mcap_mn         double precision,
  sector          text,
  raw_hash        text,
  UNIQUE (symbol, source, as_of)
);

CREATE TABLE dividend_events (
  id         bigserial PRIMARY KEY,
  symbol     text NOT NULL REFERENCES stocks(symbol),
  d_ann      date,
  d_xd       date NOT NULL,
  d_pay      date,
  dps        double precision,
  interim    text,
  fy         text,
  source     text NOT NULL DEFAULT 'lolc_dividends',
  UNIQUE (symbol, d_xd, dps, interim, source)
);
```

---

## 7. Non-goals

- Broker/CDS login automation or holdings sync  
- Replacing cse.lk prices with LOLC prices  
- Heavy multi-filter quant screener (Master Plan still gates full screener)  
- Publishing LOLC’s full board as a public Chime API dump  
- “Top undervalued stocks” / tip language  

---

## 8. Acceptance checklist (before any prod flag)

- [ ] ToS / permission decision recorded in `THIRD_PARTY_DATA.md`  
- [ ] Adapter + migration + flag default `0`  
- [ ] Rate limit + circuit breaker  
- [ ] Truncated fixtures + unit tests for parsers  
- [ ] Symbol page shows attribution + as-of  
- [ ] XD alerts dedupe proven  
- [ ] NFA copy on every user-visible surface that shows PE/DY/ratings  
- [ ] CSE price path unchanged when feed down  

---

## 9. Recommended next action

1. **Operator decision on LOLC ToS** (ask LOLC vs research-only vs skip).  
2. If go: implement **Phase 1 only** (fundamentals ingest + symbol strip + F-086).  
3. Phase 2 (XD alerts) is the highest-leverage *cherry* once Phase 1 is trusted.  
4. Keep CDS as a small Overview follow-on; leave First Capital parked.
