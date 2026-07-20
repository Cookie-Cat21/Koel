# Market Appetite Meter — Master Plan (Greed / Fear proxy)

**Status:** Plan only — not started  
**Date:** 2026-07-18  
**Authority:** [CLAUDE.md](../../CLAUDE.md) · [KOEL_MASTER_PLAN.md](KOEL_MASTER_PLAN.md) · [THIRD_PARTY_DATA.md](../THIRD_PARTY_DATA.md) · [CSE_PATH_HISTORY_PROBE.md](../experiments/CSE_PATH_HISTORY_PROBE.md) · [HYBRID_YAHOO_CSE_BARS.md](../experiments/HYBRID_YAHOO_CSE_BARS.md) · Factor catalog [FACTOR_INDEX.md](workstreams/FACTOR_INDEX.md) (F-028, F-075)  
**UI inspiration (pattern-copy only):** Tremor · shadcn Charts · shadcnblocks bullet · Magic UI NumberTicker · Ardeno bookmark set

---

## 0. One-liner

A **session + historical “market appetite” score (0–100)** for the Colombo market — breadth / intensity / participation — shown on Overview and a dedicated research page. **Not** CNN Fear & Greed (no VIX/options). **Not** buy/sell advice.

**Product name (recommended):** **Market Appetite** (bands: Extreme Caution → Caution → Neutral → Appetite → Strong Appetite).  
Avoid shipping “Greed Meter” as the primary brand — tip-adjacent. “Greed / Fear” may appear once in methodology copy as a familiar metaphor.

---

## 1. Hard truth about “2000 → today”

| Claim | Reality |
|---|---|
| CSE public JSON history to 2000 | **Impossible.** `companyChartDataByStock period=5` and `chartData period=5` top out at **~1 year** (~242 sessions). |
| Live ASPI/SL20 series from CSE | **No.** `aspiData` / `snpData` = current tick only. |
| EOD market summary deep dump | **No.** `dailyMarketSummery` ≈ **2 days per call** — must accrue forward into `market_daily_summary`. |
| Login-gated `historicalTrades` | Looks multi-year but **404 without CSE session** — deferred until ToS-clean account path. |
| Yahoo `.CM` hybrid (`hybrid_daily_bars`) | Smoke kept bars from **2000-01-03** — **research / ML panel only** (Tier D*). Must **not** be labeled CSE truth on the dash. |

### History modes we can honestly ship

| Mode | Window | Data spine | Dash label |
|---|---|---|---|
| **A — CSE truth (v1)** | ~1y rolling + forward forever | `daily_bars` + ASPI in `daily_bars` + accruing `market_daily_summary` + live `price_snapshots` | “CSE session / path” |
| **B — Research long history (v2 flag)** | ~2000 → Yahoo cutoff, then CSE | `hybrid_daily_bars` breadth reconstruct | Banner: **“Research reconstruction (Yahoo + CSE) — not CSE official”** |
| **C — Accrual forever (always on)** | From feature ship date → ∞ | Nightly job writes `market_appetite_daily` | Becomes the durable product history |

**Answer to “greed history from 2000”:**  
We can **research-reconstruct** a long series with Yahoo hybrid breadth (**Mode B**, flag-gated). We can **truthfully show** ~1y CSE + growing accrual (**Mode A+C**). We must never blend them without a clear source split.

---

## 2. Score definition (v1 — CSE only)

Compute once per session close (and optionally refresh intraday from latest snapshots).

### Inputs (all Tier A)

| Component | Weight (v1 draft) | Source | Notes |
|---|---|---|---|
| **Breadth** | 40% | Share of listed names with `change_pct > 0` | F-075 lineage; from `daily_bars` (EOD) or latest `price_snapshots` (intraday) |
| **Intensity** | 25% | Share with `|change_pct| ≥ 2%` (signed toward upside) | Caps junk one-tick noise |
| **Index day** | 20% | ASPI `change_pct` (live tick or ASPI daily bar) | `index_snapshots` / `daily_bars` symbol `ASPI` |
| **Participation** | 15% | Traded / listed ratio + turnover z-score vs 20d | Prefer `market_daily_summary` when present; else volume breadth |

Map each component to 0–100, then weighted average → **Appetite score**.

### Bands (display)

| Score | Band |
|---|---|
| 0–20 | Extreme Caution |
| 21–40 | Caution |
| 41–60 | Neutral |
| 61–80 | Appetite |
| 81–100 | Strong Appetite |

### Explicit non-inputs (v1)

- News / social sentiment (deferred — THIRD_PARTY_DATA)  
- Ownership / people graphs (orthogonal)  
- Yahoo prices on the default CSE meter  
- Any buy/sell language in reasons

### Schema (proposed)

```text
market_appetite_daily (
  trade_date date PRIMARY KEY,
  score double precision NOT NULL,          -- 0..100
  band text NOT NULL,
  components jsonb NOT NULL,               -- {breadth, intensity, index, participation, …}
  source text NOT NULL,                   -- 'cse' | 'hybrid_research'
  universe_n int NOT NULL,
  advancers int, decliners int, unchanged int,
  aspi_change_pct double precision,
  computed_at timestamptz NOT NULL
)

market_appetite_intraday (
  ts timestamptz PRIMARY KEY,
  score …, components …, source='cse_snapshots'
)  -- optional; prune to current session
```

CLI: `python3 -m koel appetite-backfill` (CSE 1y) · `appetite-backfill --hybrid` (research, flag).  
Poller/tick: recompute intraday stub; finalize row at session close.

---

## 3. What we can *do* with greed / appetite history

Once daily scores exist, these product surfaces unlock:

| Use | Mode | Value |
|---|---|---|
| **Today’s meter** on Overview | A | Instant “how hot is the tape?” |
| **1Y history chart** | A | See regime shifts within CSE-truth window |
| **MAX history chart** | B (flag) or C (after years of accrual) | Long-run context; B needs research banner |
| **Band chronology** (90-day color ticks) | A | “How long have we been in Appetite?” |
| **Δ vs yesterday / week / month** | A | KPI strip |
| **Telegram optional alert** | A | “Appetite crossed into Strong Appetite” — cherry, flag-gated, NFA |
| **Signal Board regime gate** | A | Soft factor: down-weight momentum tips when Extreme Caution (describe, don’t advise) |
| **ML feature** `mkt_breadth` / appetite | A or B | F-075; hybrid only inside research training |
| **Symbol page context chip** | A | “Market Appetite 72 · Appetite” next to quote (not a tip) |
| **Crisis / boom annotations** | B/C | Manual or rule-based markers (e.g. large ASPI drawdowns) on long chart |
| **Export / API** `GET /api/v1/appetite` | A | Session + history for dash |

### What history is *not* for

- Predicting next-day winners  
- “Buy when Extreme Caution” narratives  
- Showing Yahoo-era scores as “official CSE greed since 2000” without the research banner

---

## 4. UI plan (elements found)

**Stack decision:** Stay on Quiverly (Next.js + Tailwind + shadcn + existing SVG/`motion`).  
**Do not** add `@tremor/react` or Magic UI packs unless brush/zoom forces Recharts later.  
**License fence:** no React Bits Commons Clause / unpaid Pro-only blocks in product — **pattern-copy** only.

### Patterns to copy (from Ardeno UI set + docs)

| Element | Source | Role in Quiverly |
|---|---|---|
| **Bullet chart / qualitative zones** | [shadcnblocks chart-card26](https://www.shadcnblocks.com/block/chart-card26) | Best Fear↔Appetite metaphor — horizontal zones + marker |
| **ProgressBar / Tracker** | [Tremor ProgressBar](https://tremor.so/docs/visualizations/progress-bar), [Tracker](https://tremor.so/docs/visualizations/tracker) | Spectrum track; 90d band ticks |
| **Spark / Area** | [Tremor Spark charts](https://tremor.so/docs/visualizations/spark-charts), [AreaChart](https://tremor.so/docs/visualizations/area-chart) | Overview spark; `/appetite` history |
| **Radial / arc gauge** | [shadcn radial charts](https://ui.shadcn.com/charts/radial) | Optional `/appetite` hero only |
| **Interactive area chips** | [shadcn.io area-interactive](https://www.shadcn.io/charts/area-interactive) | `3M \| 1Y \| 5Y \| MAX` (MAX = hybrid or accrual) |
| **NumberTicker** | [Magic UI](https://magicui.design/docs/components/number-ticker) | Optional score count-in on dedicated page |
| **Existing Quiverly** | `KpiStrip`, `IndexStrip`, `SectorHeatStrip`, `Sparkline`, `ExpandablePriceChart` chips, `NfaInline`/`NfaFooter` | **Default building blocks** |

### What not to ship

- KPI card walls (4–8 identical StatCards)  
- Purple/indigo glow gauges, emoji band labels  
- Donut/pie for a bipolar continuum  
- Tremor npm dependency for v1  
- “Best time to buy” copy

### Surfaces

**Overview widget (v1)** — one strip beside index/sectors:

1. Score (mono) + band label  
2. Horizontal 5-zone spectrum + needle  
3. ~60d spark + Δ1d  
4. Link → `/appetite` + `<NfaInline />`

**/appetite page (v1.5)**

1. Hero meter (spectrum or 180° arc)  
2. `KpiStrip`: Score · Band · Δ1d · Δ1w · Days-in-band · Universe N  
3. History chart + range chips; brush only if MAX needs it  
4. Tracker row (last 90 sessions)  
5. Methodology + source split (CSE vs research) + `<NfaFooter />`

### A11y / NFA

- `role="meter"` `aria-valuemin=0` `aria-valuemax=100` `aria-valuetext="72 — Appetite"`  
- Band text always beside color  
- `prefers-reduced-motion` skips ticker springs  
- NFA under score on Overview; footer on dedicated page

---

## 5. Phased build (fence-legal)

### Phase 0 — Spec lock (no UI)

- Finalize weights + band cut points  
- Name: **Market Appetite**  
- Migration stub for `market_appetite_daily`

### Phase 1 — CSE truth meter (ship)

- Job: compute daily score from `daily_bars` / snapshots + ASPI  
- Backfill ~1y after full `path-backfill` + `aspi-backfill`  
- Accrue `market_daily_summary` nightly (participation)  
- Overview strip + `GET /api/v1/appetite`  
- Implements spirit of **F-075** (`mkt_breadth`)

### Phase 2 — Dedicated page + history UX

- `/appetite` with 3M/1Y charts, Tracker, methodology  
- Optional Telegram cross-band alert (flag)

### Phase 3 — Research long history (flag)

- `appetite-backfill --hybrid` → `source='hybrid_research'`  
- MAX chart only when `APPETITE_HYBRID_HISTORY=1`  
- Persistent research banner; never default on Overview

### Phase 4 — Soft Signal Board gate (optional)

- Expose appetite as a descriptive regime chip / factor  
- Still NFA; no tip language

### Explicitly out of scope

- CNN-style options/VIX clone  
- News-sentiment greed (until Tier B/C checklist clears)  
- Portfolio “what to buy in greed”  
- Competitor scrape for history

---

## 6. Data / ops checklist

```bash
# CSE spine for Phase 1
python3 -m koel path-backfill --force --limit 0
python3 -m koel aspi-backfill --force
python3 -m koel market-summary-backfill --force   # accrue; repeat over days
# later:
python3 -m koel appetite-backfill --force

# Research-only Phase 3
HYBRID_BACKFILL_ENABLED=1 python3 -m koel hybrid-backfill --force --limit 0
APPETITE_HYBRID_HISTORY=1 python3 -m koel appetite-backfill --hybrid --force
```

Verify:

```sql
SELECT min(trade_date), max(trade_date), count(*), source
FROM market_appetite_daily GROUP BY source;
```

---

## 7. Success criteria

| Criterion | Pass |
|---|---|
| Overview shows today’s score without blank empty state after backfill | Yes |
| 1Y chart uses only `source='cse'` by default | Yes |
| MAX/hybrid never unlabeled as CSE | Yes |
| No buy/sell language in UI or Telegram copy | Yes |
| F-075 breadth component queryable from components JSON | Yes |
| Dash never calls cse.lk / Yahoo | Yes |

---

## 8. Open decisions (for product owner)

1. **Primary name:** Market Appetite (recommended) vs Greed Meter?  
2. Ship Overview strip in Phase 1, or page-first?  
3. Enable Phase 3 hybrid MAX on production with research banner, or keep hybrid local/research only?  
4. Telegram cross-band alerts — on or cherry-later?

---

## 9. Relationship to recent work

Ownership / People graph densify is **orthogonal** — nice for research dossiers, **not** an input to appetite.  
Greed/appetite is a **breadth + tape** feature on top of `daily_bars` / snapshots / market summary.

Research only — not financial advice.
