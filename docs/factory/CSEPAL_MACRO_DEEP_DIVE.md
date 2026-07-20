# CSEPal `/macro` deep dive → koel plan

**Date:** 2026-07-20  
**Reference (observe only — do not scrape):** https://csepal.lk/macro  
**Authority:** [CLAUDE.md](../../CLAUDE.md) · [KOEL_EDGE_VS_CSEPal_MASTER_PLAN.md](KOEL_EDGE_VS_CSEPal_MASTER_PLAN.md) · [GREED_METER_MASTER_PLAN.md](GREED_METER_MASTER_PLAN.md) · [THIRD_PARTY_DATA.md](../THIRD_PARTY_DATA.md) · [FACTOR_INDEX.md](workstreams/FACTOR_INDEX.md)

---

## 0. Verdict

CSEPal’s Macro surface is a **paid market-intel terminal**: Fear & Greed gauge + a tab farm of foreign flow, order-book depth history, microstructure stats, CDS ownership, FX/commodities, food prices, tourism, world markets, and gated news/shareholder tools.

koel already ships the **honest CSE-native core** of that story as **Market Appetite** (Overview + `/appetite`), plus indexes/sectors/movers and per-symbol book alerts. We are **not** missing a Fear & Greed brand — we are missing a **thin market-tape strip** (foreign net, market-wide book pressure) and **Telegram cherry** on those regimes.

**Do not clone `/macro`.** Steal the *pulse* (one viewport answers “what’s the tape doing?”) and keep koel’s wedge: dash clarity + explainable research + push when the tab is closed.

---

## 1. What CSEPal `/macro` actually is

SPA (`MacroViewPage`); APIs under `/api/market/*` are bot-gated (403 from this environment). Inventory below is from the shipped frontend chunk + public LinkedIn product posts — **UI observation only**.

### 1.1 Focus sidebar (top-level modules)

| Module | What it shows | Monetization signal |
|---|---|---|
| **CSE** | Index / tape context tied to greed + pressure | Core free surface |
| **Daily CSE Statistics** (“Market Insights”) | Tabbed chart wall (see §1.2) | Entitlement `market_insights` + monthly quota |
| **World Markets** | Global indices / VIX-style tiles with mini history | Separate feed job |
| **Asset / FX Rates** | USD·EUR·GBP·INR·SGD / LKR, crude (Brent/WTI), gold, etc. | External prices sync |
| **Food Prices** | SLTDA-adjacent basket (rice, oils, onions, fish/meat…) | Domestic CPI-proxy storytelling |
| **Tourism** | Arrivals, YoY, source-market concentration | Official monthly series |
| **News Insights / Media** | News sentiment trend + story feed | Login + quota (`market_media_sentiment`) |

### 1.2 Daily CSE Statistics tabs (the dense middle)

Observed chart / KPI families:

| Tab / pane | Metrics (labels in UI) | Data implication |
|---|---|---|
| **Foreign Flow** | Purchases vs sales, **net foreign**, foreign share of turnover, top foreign movers | Needs daily market summary + history accrual |
| **Market Depth** | Bid/ask near-touch / L4–5 / deep>5 stacked over **1Y**, ASPI overlay (“Market Depth Evolution”) | Persistent **market-wide** L2 history (deeper than public CSE totals) |
| **Microstructure / Liquidity** | Median spread %, imbalance %, bid/ask ratio, liquidity surge/drop, price impact | Cross-sectional book + trade stats over time |
| **Volume Profile** | HHI volume concentration, skewness, kurtosis, tail volume shares, range % of VWAP | Day-tape distribution aggregates |
| **Pressure & Crowding** | Buy pressure / sell pressure, market pressure %, correlation regime | Crowding / A-D style composites |
| **Breadth & Participation** | Advancers/decliners, weighted breadth, % traded, % above MAs, participation | Cross-section of listings |
| **Valuation** | Market P/E, P/B, DY regime | Fundamentals universe + aggregation |
| **Participation / Turnover** | Total turnover, trades/stock, zero-turnover counts | EOD market summary |
| **CDS Ownership** | Domestic vs foreign holding qty/value %, trade-count split | CDS / custody series (not cse.lk trade JSON alone) |
| **Volatility & Regime** | Range expansion, dispersion, “fundamental regimes” verdicts | Custom regime model |
| **Crossings / Shareholder** | Crossing history, shareholder concentration search | **Locked** paid features |

### 1.3 Fear & Greed card (product hero)

From product screenshot / UI copy:

- Branding: **“CSE Macro Sentiment · Fear & Greed Index”**
- Score 0–100 with CNN-style bands: X Fear · Fear · Neutral · Greed · X Greed
- Gauge + needle + “As of” + **coverage %**
- LinkedIn daily blurb packages: orderbook gap, F&G band, buy/sell pressure, foreign flow sign, crude oil

koel’s deliberate rename (**Market Appetite**, Caution→Appetite bands) is the compliance-safer twin — already planned in [GREED_METER_MASTER_PLAN.md](GREED_METER_MASTER_PLAN.md) and **shipped** on Overview/`/appetite`.

### 1.4 Business model note

Credits / Lemon Squeezy / local-transfer billing + feature entitlements. Macro is partly a **funnel into paid intel**, not just a free overview. koel’s wedge stays Telegram + cake, not credit-gated chart farms.

---

## 2. Gap matrix (CSEPal Macro vs koel today)

| Capability | CSEPal `/macro` | koel today | Gap type |
|---|---|---|---|
| Session sentiment 0–100 | Fear & Greed gauge | **Market Appetite** strip + `/appetite` history | **Parity (done)** — keep our naming/NFA |
| ASPI / SL20 pulse | Header + overlays | Overview `IndexStrip` | Parity |
| Sector heat | Elsewhere in product | Overview sectors | Parity (thin) |
| Breadth / participation | Dedicated charts | Inside Appetite components (40/15 weights) | Partial — not a standalone Macro tab |
| Foreign purchases / sales / net | First-class charts + daily LinkedIn blurb | Stored in `market_daily_summary` (`equity_foreign_*`, `foreign_net`) — **no dash UI** | **High-value thin ship** |
| Market-wide order-book gap / pressure | Market Depth Evolution + Pressure pane | Per-symbol `order_book_snapshots` + `bid_heavy`/`ask_heavy` alerts; nightly top-25 accrual | **Partial** — need market aggregate + history UI |
| Buy/sell pressure (tape) | Explicit series | Proxies only (`volup`/`voldown`); CSE has no aggressor tags | Honest proxy only — don’t fake |
| CDS domestic/foreign ownership | Charts | Candidate CDS INFOLINE monthly (ToS checklist); LOLC StockLens **banned** | Defer / thin monthly if ToS OK |
| World markets / oil / FX | Live tiles | Tier B macros F-091…096 **DEFER** until ToS intake | Defer |
| Food basket / tourism | Full modules | F-097…098 DEFER | Defer (not wedge) |
| News / social sentiment | Gated | Deferred (`THIRD_PARTY_DATA`) | Defer |
| Valuation regime (mkt PE/PB) | Charts | Sparse NAV/ROE extract still Phase C | Later, after fundamentals densify |
| Volume-profile intelligence (HHI, kurtosis…) | Charts | Not productized | Research/ML only unless proven |
| Shareholder / crossings intel | Paid locks | Ownership graph exists (different job) | Don’t clone; deepen ownership map |
| Daily “macro update” push | LinkedIn / in-app | Telegram is our channel — **no appetite/foreign/book regime alerts yet** | **Cherry gap** |
| Dense Macro terminal IA | Full `/macro` app section | Explicit non-goal (desk terminal) | **Reject wholesale clone** |

---

## 3. What we should *not* do

Copied from fence docs — auto-fail if a loop tries these:

1. **No CSEPal Macro clone page** with 8–12 analysis tabs.  
2. **No competitor scrape** of csepal.lk APIs or HTML.  
3. **No Tier B FX/oil/world/food/tourism adapters** until [THIRD_PARTY_DATA.md](../THIRD_PARTY_DATA.md) intake checklist is green.  
4. **No LOLC / broker holdings scrape** (Tier E).  
5. **No “Fear & Greed” as primary product name** (tip-adjacent); keep **Market Appetite**.  
6. **No buy/sell language** in reasons or Telegram copy.  
7. **No paid L2 depth farm** pretending public `orderBook` totals are full Market Depth Evolution.  
8. **No portfolio / credits / Lemon Squeezy** path as a response to their monetization.

---

## 4. Plan we *can* do (fence-legal)

North star: Overview answers “what’s the tape doing?” in **one composition**, and Telegram can ping when that regime flips — without becoming a macro terminal.

### Phase M0 — Honesty + accrual (ops, no new IA)

| ID | Work | Why |
|---|---|---|
| M0.1 | Keep nightly `market_daily_summary` upsert (B-011) until ≥60–90 sessions | Unlocks foreign + participation history |
| M0.2 | Keep order-book snapshot accrual (B-001); expand beyond alert-only symbols to a **stable market sample** (e.g. top-N by turnover + watchlist union) | Needed for market-wide imbalance series |
| M0.3 | Document coverage % on Appetite (universe_n / listed) like CSEPal’s “Coverage” chip — we already have the fields | Trust parity |

**Exit:** Neon/`market_daily_summary` row count trending up; `order_book_snapshots` multi-day.

### Phase M1 — Thin “Tape pulse” on Overview (ship)

One strip / bento cell — **not** a new `/macro` route.

| ID | Deliverable | Source (Tier A) | Acceptance |
|---|---|---|---|
| M1.1 | **Foreign net chip** — today’s `foreign_net` + Δ vs prior row; spark of last ~20 sessions when history exists | `market_daily_summary` | Null-safe; “as of trade_date”; NFA |
| M1.2 | **Market book pressure chip** — mean `totalBids/(totalBids+totalAsks)` (or imb %) across latest OB sample | `order_book_snapshots` | Label as “public book totals sample”, not L2 |
| M1.3 | Wire chips beside existing Appetite + Index strips | Overview only | First viewport still one composition; no card wall |
| M1.4 | `GET /api/v1/market/tape` (or extend `/appetite`) returning `{foreign, book, as_of}` | Postgres only | web never calls cse.lk |

**Exit:** Overview shows Appetite · Foreign · Book without a Macro nav item.

### Phase M2 — Cherry: regime Telegram alerts

| ID | Alert | Trigger (draft) | Flag |
|---|---|---|---|
| M2.1 | `appetite_band` | Band crosses (e.g. Caution→Appetite) once/day | `TELEGRAM_APPETITE_ALERTS=0` default |
| M2.2 | `foreign_flow` | `|foreign_net|` ≥ user threshold or sign flip vs 5d median | opt-in `/alert MARKET foreign …` |
| M2.3 | `book_pressure` | Market imb % ≥ threshold for N consecutive ticks | opt-in |

Copy rules: descriptive (“Market Appetite moved to Strong Appetite · score 84”) + NFA footer. **No oil/FX in v1 alerts.**

**Exit:** User can arm market-wide regime pings; fires appear in alert history with “Telegram sent ✓”.

### Phase M3 — Research page densify (optional, still thin)

Extend `/appetite` (or `/market` research section) — **one** secondary page, not CSEPal’s tab farm:

1. Appetite hero (existing)  
2. Foreign net / share-of-turnover chart when ≥20 summary days  
3. Market book imbalance history when ≥10 sessions of samples  
4. Methodology: what is CSE truth vs “sample aggregate”  
5. Link to Signal Board (regime soft-factor later)

Still banned on this page: world markets wall, food basket, tourism heatmap, news unlock CTAs, depth L1–L5 stacks.

### Phase M4 — Signal Board soft factors (after history exists)

| Factor | Status today | Plan |
|---|---|---|
| F-075 mkt breadth | OPEN / Appetite lineage | Fold Appetite components into `symbol_scores` context chip |
| F-028 sector rotation breadth | OPEN | After M1 data stable |
| Foreign-flow session factor | not numbered | Add only as **descriptive** component once M0 history ≥60d |
| F-091…100 external macro | DEFER | Unchanged — ToS gate |

### Phase M5 — Explicit defer list (revisit only with intake)

| CSEPal module | koel stance |
|---|---|
| World Markets tiles | Defer (Tier B/D) |
| Crude / gold / FX cards | Defer (F-091/095) |
| Food prices basket | Out of wedge |
| Tourist arrivals | Out of wedge (unless CBSL/SLTDA ToS-clean **and** product asks) |
| News Insights / media sentiment | Defer |
| Market Depth Evolution (L2 stacks) | Reject on public API; revisit only with licensed CSE depth feed |
| CDS ownership charts | Thin monthly CDS INFOLINE candidate only |
| Shareholder search / crossings paid tools | Don’t clone; keep ownership graph / people map |

---

## 5. Implementation sketch (when building)

```
poller/tick
  ├─ upsert market_daily_summary          # already
  ├─ sample order books → snapshots       # widen sample (M0.2)
  └─ finalize market_appetite_daily       # already

storage / API
  └─ GET /api/v1/market/tape              # foreign + book aggregates

web Overview
  └─ TapePulseStrip next to AppetiteStrip # M1

chime rules + bot
  └─ MARKET appetite/foreign/book alerts  # M2
```

**Files likely to touch (future PR, not this doc):**  
`chime/poller.py`, `chime/storage.py`, `chime/rules.py`, `chime/domain.py`, `web/src/app/overview/page.tsx`, new `web/src/lib/api/tape.ts` + small strip component, migrations only if aggregate tables needed (prefer derive-from-existing first).

---

## 6. Success rubric (anti-CSEPal)

| Axis | Pass |
|---|---|
| Completeness feel | User sees Appetite + foreign sign + book pressure without leaving Overview |
| Cherry | ≥1 market-regime Telegram alert type armed + delivered |
| Honesty | Public-book / accrual limits labeled; no fake L2 depth |
| Fence | No `/macro` clone, no competitor scrape, no Tier B without checklist |
| Differentiation | Still obviously koel (push + research), not a desk Macro terminal |

Fail if Overview grows a second scroll of chart tabs, or if we ship “Fear & Greed” as the primary brand.

---

## 7. Suggested build order (smallest → sharpest)

1. **M0** accrual health check (counts on `/health` or ml-health — may already exist).  
2. **M1.1** foreign chip from existing table (fastest UI win).  
3. **M1.2–M1.3** book pressure sample + Overview composition.  
4. **M2.1** Appetite band Telegram alert (reuses shipped score).  
5. **M2.2** foreign-flow alert once history is non-trivial.  
6. **M3** charts on `/appetite` only if M1 feels cramped.  
7. Everything in **M5** stays parked.

---

## 8. One-liner for the team

CSEPal Macro is a **subscription intel terminal**; koel should answer the same daily question with a **three-signal tape pulse** (Appetite · Foreign · Book) and **Telegram when it flips** — using data we already accrue — not by rebuilding their tab farm.
