# koel Macro Expansion — Master Plan

**Status:** Active planning (2026-07-20)  
**Unlock:** Product asks for Oil / FX / world / food / tourism / news as **additive layers** on top of the CSE wedge — not a CSEPal Macro clone.  
**Authority:** [CLAUDE.md](../../CLAUDE.md) · [CSEPAL_MACRO_DEEP_DIVE.md](CSEPAL_MACRO_DEEP_DIVE.md) · [GREED_METER_MASTER_PLAN.md](GREED_METER_MASTER_PLAN.md) · [KOEL_EDGE_VS_CSEPal_MASTER_PLAN.md](KOEL_EDGE_VS_CSEPal_MASTER_PLAN.md) · [THIRD_PARTY_DATA.md](../THIRD_PARTY_DATA.md) · [FACTOR_INDEX.md](workstreams/FACTOR_INDEX.md) F-091…100  
**Competitor reference:** https://csepal.lk/macro — observe UI only; **never scrape**.

---

## 0. Product stance (updated)

| Layer | Job | Default |
|---|---|---|
| **Cake (CSE)** | Symbols, watchlist, alerts, Appetite, foreign, book pressure | Always on |
| **Cherry (Telegram)** | Push when tape / macro / watchlist rules fire | Opt-in per rule |
| **Context (Tier B+)** | Oil, FX, world, food, tourism, news — “why the tape feels like this” | **Additive**, flag-gated, fail-soft |
| **Research (Signal Board)** | Explainable scores; optional macro factors once history exists | Opt-in overlays; NFA |

**Yes — we can build the context layer.** It is no longer “out of wedge” as a hard ban; it is a **second product surface** that must not:

1. Steal first-viewport space from CSE cake  
2. Call upstream from `web/`  
3. Ship without ToS/attribution logged in `THIRD_PARTY_DATA.md`  
4. Use buy/sell language or tip-adjacent “Fear & Greed” as the primary brand  

**IA rule:** Overview stays a **tape pulse**. New route `/context` (or `/macro` if we want the familiar word) holds the dense modules. Nav label: **Context** preferred over cloning CSEPal’s “Macro” brand, unless marketing insists.

---

## 1. How we beat CSEPal (research → differentiation)

CSEPal wins on **chart density + paid intel unlocks**. koel should win on **clarity, push, honesty, and CSE-native linkage**.

| Axis | CSEPal Macro | koel better move |
|---|---|---|
| Delivery | In-app / credits / LinkedIn blurb | **Telegram daily “tape brief” + threshold alerts** when tab closed |
| Sentiment brand | CNN-style Fear & Greed | Keep **Market Appetite** (NFA-safer) + optional “similar to F&G” in methodology only |
| Foreign / book | Deep chart farm | **Same signals, smaller UI** + alert when sign flips |
| Oil / FX | Tiles in Macro | **CBSL USD/LKR as local truth** + EIA oil with attribution; show **Δ vs CSE Appetite** correlation chip (descriptive) |
| Food / tourism | Standalone story modules | Tie to **sector chips** (Hotels/Travel, Food & Beverage, Plantations) — “arrivals YoY ↑ · related sector RS” not a grocery terminal |
| News | Gated sentiment dashboard | Prefer **CSE disclosures + notices first**; external headlines as thin link-out strip with ToS; optional Gemini brief already gated |
| Trust | Opaque freshness | **Source + as-of + poller age** on every context card |
| Paywall | Quotas on insights | Core context free; never credit-gate foreign/appetite |
| Depth Evolution | Implies rich L2 history | Label public book sample honestly; don’t fake L4–L5 stacks |
| Action | Browse charts | **One tap → watch / alert** from any context card that mentions a symbol or sector |

**Kill criteria for “better”:** if a module cannot (a) explain a CSE move, (b) arm a Telegram rule, or (c) feed a Signal Board factor within one release after ship — park it.

---

## 2. Source research snapshot (2026-07-20)

Intake checklist still required before any prod flag flips to `1`. Status = research readiness, not license clearance.

### 2.1 FX / rates

| Source | What | Reachable? | License note (research) | koel use |
|---|---|---|---|---|
| **CBSL** daily indicative FX | USD/LKR + EUR/GBP/INR/SGD/AED… vs LKR | HTML tool `cbsl.gov.lk/cbsl_custom/exrates/exrates.php` **200**; also spreadsheet downloads on rates pages | Official public stats; confirm redistribution/attribution before prod | **Primary LKR truth** (F-091) |
| **Frankfurter** (ECB-derived) | USD↔EUR/GBP/INR/SGD… | API works; **LKR not in currency set** | ECB open with attribution; MIT API | Cross-check world FX only — **never** replace CBSL for LKR |
| Commercial FX APIs | Fluentax etc. | n/a | Paid / Tier D | Defer |

**Better than CSEPal:** stamp every FX chip `Source: CBSL · as of <date>` and Telegram `/alert MARKET usd N%` for daily move.

### 2.2 Oil / commodities

| Source | What | License note | koel use |
|---|---|---|---|
| **EIA Open Data API** | Brent + WTI spot (daily) | US gov **public domain**; attribution required; free API key | F-095; Overview/Context oil chip |
| datasets/oil-prices (DataHub) | Packaged EIA series | PDDL / public domain packaging | Optional research backfill only |

**Better:** show oil Δ **next to energy / diversified holdings sector RS**, not a standalone commodity desk.

### 2.3 World markets

| Source | What | Caveat | koel use |
|---|---|---|---|
| Yahoo / Stooq-style index history | S&P, Nikkei, Hang Seng, India, VIX proxies | Unofficial; bot walls; ToS gray → **Tier D\*** research pattern like hybrid bars | Flag-gated research panel only |
| Index **EOD snapshots** via polite public JSON (if ToS-clean found) | Same | Prefer official/open | Thin “overnight tape” strip |
| Finnhub / Polygon | Clean APIs | Tier D commercial | Defer until revenue |

**Better:** don’t build CSEPal’s world-market wall. Ship **5 tiles max** (US / Europe / Asia / India / VIX-proxy) with “research / delayed” banner, plus Telegram “global risk-off session” only when CSE Appetite also extreme.

### 2.4 Food prices

| Source | What | Reachable? | koel use |
|---|---|---|---|
| **DCS Weekly Retail Prices** | Colombo district basket dashboard | `statistics.gov.lk/DashBoard/Prices/` **200** | Staples pressure index (rice/coconut oil/onions…) |
| **CBSL Daily Price Report** | Key consumer items PDF/HTML | Published daily | Optional denser daily series |
| CCPI / NCPI monthly | Official inflation | DCS | F-093 surprise vs prior |

**Better than grocery porn:** one **Food pressure score** (0–100) + YoY on 6–8 staples, linked to Food Retail / Consumer sectors — not 40 SKU charts.

### 2.5 Tourism

| Source | What | Reachable? | koel use |
|---|---|---|---|
| **SLTDA** Excel/PDF arrivals by country | Monthly + weekly reports | Portal **200**; Excel downloads listed through 2026-05 | F-097; Hotels/Travel sector chip |
| World Bank `ST.INT.ARVL` | Annual arrivals | API works but **recent years null** in probe | Historical only; not dash truth |

**Better:** “Arrivals MoM/YoY + top source markets” → auto-highlight **hotel / leisure symbols on watchlist**, not a tourism ministry clone.

### 2.6 News / sentiment

| Source | What | Stance |
|---|---|---|
| CSE `approvedAnnouncement` / disclosures | Already in koel | **Primary** — keep investing here |
| Gemini filing briefs | Flag-gated today | Keep; never default-on |
| EconomyNext / Daily FT / Ada Derana Biz | Headlines | **No scrape of full text** without license; RSS/link-out only after ToS |
| Social feed (CSEPal-style) | Opaque | Skip v1 |

**Better:** news = **disclosure-first timeline** + optional “external headline links” strip. Sentiment score only if we own the corpus (CSE titles) or have a licensed feed.

### 2.7 Already in-house (ship before Tier B)

| Series | Table / code | UI today |
|---|---|---|
| Market Appetite | `market_appetite_daily` | Overview + `/appetite` |
| Foreign purchase/sales/net | `market_daily_summary` | **Missing UI** |
| Order book samples | `order_book_snapshots` | Per-symbol alerts only |
| ASPI / SL20 / sectors | indexes + sectors APIs | Overview |

---

## 3. Architecture (locked)

```
adapters (Python, flag-gated)
  ├─ cbsl_fx / eia_oil / dcs_food / sltda_tourism / world_indexes(*)
  └─ shared: rate limit · circuit breaker · attribution fields

Postgres
  ├─ macro_series (source, series_id, ts, value, unit, raw_hash)
  ├─ macro_snapshots_daily (trade_date, payload jsonb)  -- denormalized dash row
  └─ existing market_daily_summary / appetite / order_book_*

chime jobs
  └─ macro-tick (cron; outside CSE hours OK)

web/
  ├─ Overview: TapePulse (Appetite · Foreign · Book) + optional 2 context chips
  ├─ /context: modules (FX, Oil, World, Food, Tourism, News links)
  └─ never calls upstream
```

Flags (all default `0` until intake green):

```
MACRO_CONTEXT_ENABLED
CBSL_FX_ENABLED
EIA_OIL_ENABLED
DCS_FOOD_ENABLED
SLTDA_TOURISM_ENABLED
WORLD_INDEX_RESEARCH_ENABLED
MACRO_TELEGRAM_BRIEF_ENABLED
```

---

## 4. Phased roadmap

### Phase 0 — Governance (before any adapter)

| ID | Work |
|---|---|
| P0.1 | Copy intake checklist into `THIRD_PARTY_DATA.md` per source (CBSL, EIA, DCS, SLTDA) |
| P0.2 | Confirm attribution strings + fail-soft UX copy |
| P0.3 | Schema migration stub `macro_series` + `macro_snapshots_daily` |
| P0.4 | Agree IA: Overview pulse vs `/context` modules |

### Phase 1 — CSE tape pulse (no Tier B required)

*From [CSEPAL_MACRO_DEEP_DIVE.md](CSEPAL_MACRO_DEEP_DIVE.md) M0–M2 — do this first.*

| ID | Deliverable |
|---|---|
| P1.1 | Foreign net chip + spark from `market_daily_summary` |
| P1.2 | Market book pressure from OB sample aggregate |
| P1.3 | Overview composition: Appetite · Foreign · Book |
| P1.4 | Telegram: appetite band / foreign / book alerts |

**Exit:** Overview answers “what’s the CSE tape doing?” without leaving cake.

### Phase 2 — Local official macros (highest CSE relevance)

| ID | Deliverable | Source |
|---|---|---|
| P2.1 | USD/LKR (+ EUR/GBP/INR) daily series + Overview/Context chip | CBSL |
| P2.2 | Telegram `/alert MARKET usdlkr P%` | CBSL |
| P2.3 | Brent (+ optional WTI) daily + energy-sector link chip | EIA |
| P2.4 | Optional Signal Board soft factors F-091 / F-095 (describe only) | after ≥60 days history |

**Exit:** Local FX + oil live, attributed, flag-gated.

### Phase 3 — Domestic real-economy context

| ID | Deliverable | Source |
|---|---|---|
| P3.1 | Food pressure index (small staple basket) + YoY | DCS weekly retail |
| P3.2 | Tourism arrivals MoM/YoY + top sources | SLTDA Excel |
| P3.3 | Sector bridge chips → `/market?sector=` | in-house sectors |
| P3.4 | CCPI monthly print card (F-093) | DCS |

**Exit:** `/context` has Food + Tourism modules that deep-link into CSE sectors.

### Phase 4 — World tape (research-honest)

| ID | Deliverable |
|---|---|
| P4.1 | ≤5 world tiles, delayed, research banner |
| P4.2 | Overnight brief Telegram only when global move large **and** next CSE Appetite extreme |
| P4.3 | Keep hybrid/Yahoo patterns off default “CSE truth” labels |

### Phase 5 — News (disclosure-first)

| ID | Deliverable |
|---|---|
| P5.1 | Densify CSE disclosure/notice timeline on Overview + `/context` |
| P5.2 | External headline **link-out** strip after ToS (no full-text scrape) |
| P5.3 | Optional title-only sentiment on CSE announcements (in-house NLP / Gemini) |
| P5.4 | Skip social-feed clone |

### Phase 6 — Composite + polish

| ID | Deliverable |
|---|---|
| P6.1 | Macro composite regime card (F-100) — weights documented, NFA |
| P6.2 | Daily Telegram “Tape brief” (Appetite, foreign, USD/LKR, oil, 1 disclosure highlight) |
| P6.3 | Adversarial pass: terminal? tip language? license? Overview clutter? |

---

## 5. UI composition rules

### Overview (first viewport)

Allowed:

1. Brand / session honesty (poller age)  
2. Indexes  
3. **Tape pulse:** Appetite · Foreign · Book  
4. Optional **two** context chips max (e.g. USD/LKR, Oil) — collapse to `/context`  

Not allowed on first viewport: food SKU grids, tourism heatmaps, world-market walls, news article lists, valuation tab farms.

### `/context` page

One module per section (headline + one sentence + one viz + source line). Progressive disclosure; no paywall. Mobile: stacked modules, not CSEPal sidebar tab explosion.

### Telegram

| Brief | Cadence |
|---|---|
| Threshold alerts | Immediate (existing pattern) |
| Optional daily tape brief | Once after CSE close (flag) |
| Weekly tourism/food | Only if user subscribed |

---

## 6. Schema sketch

```sql
-- illustrative; finalize in migration when P0 lands
CREATE TABLE macro_series (
  source text NOT NULL,          -- 'cbsl_fx' | 'eia_oil' | 'dcs_food' | 'sltda_tourism' | ...
  series_id text NOT NULL,       -- 'USD_LKR' | 'BRENT_SPOT' | ...
  ts timestamptz NOT NULL,
  value double precision NOT NULL,
  unit text,
  as_of_date date,
  attribution text NOT NULL,
  raw_hash text,
  PRIMARY KEY (source, series_id, ts)
);

CREATE TABLE macro_snapshots_daily (
  trade_date date PRIMARY KEY,
  payload jsonb NOT NULL,         -- denormalized chips for Overview
  computed_at timestamptz NOT NULL
);
```

---

## 7. Factor unlock map

| Factor | Phase | Gate |
|---|---|---|
| F-091 FX | P2 | CBSL intake green |
| F-092 policy rate | later | CBSL rates page intake |
| F-093 CPI | P3 | DCS CCPI intake |
| F-095 oil | P2 | EIA key + attribution |
| F-096 EM/world | P4 | research flag only |
| F-097 tourism | P3 | SLTDA intake |
| F-098 rainfall/agri | park | needs Met dept source |
| F-099 tariff news | park | notices NLP first |
| F-100 composite | P6 | after ≥3 Tier B series live |

Until intake is checked off in `THIRD_PARTY_DATA.md`, factor status stays **DEFER** in `FACTOR_INDEX.md` even though this master plan is active.

---

## 8. Suggested build order (practical)

1. **P1 tape pulse** (foreign + book + Telegram) — pure Tier A, immediate product win  
2. **P0 intake** for CBSL + EIA (fastest clean macros)  
3. **P2 FX + oil**  
4. **P3 tourism** (Excel monthly — easy) then **food** (dashboard parsing harder)  
5. **P5 disclosure densify** before external news  
6. **P4 world** last (ToS / quality weakest)  
7. **P6 brief + composite**

---

## 9. Success rubric

| Axis | Pass |
|---|---|
| Additive | Context modules hide cleanly when flags=0 |
| Honesty | Every card has source + as-of; research banners where needed |
| Cherry | ≥3 market-level Telegram alert types (appetite/foreign/FX or oil) |
| Cake first | Overview first viewport still CSE tape, not macro desk |
| License | No prod series without checklist row |
| Differentiation | Daily tape brief + sector bridges beat chart-farm parity |

Fail if we ship a CSEPal Macro clone, scrape csepal.lk, or put food/tourism/world walls above the fold on Overview.

---

## 10. One-liner

Ship **CSE tape pulse + Telegram first**, then add **official Sri Lanka + EIA context** as a separate `/context` surface — attributed, flag-gated, sector-linked — and only then touch world/news. That’s how koel gets CSEPal’s *useful macros* without becoming their terminal.
