# Macro build — 20 improvement loops vs CSEPal `/macro`

**Date:** 2026-07-20  
**Branch work:** tape pulse + `/context` + CBSL/EIA adapters + MARKET Telegram alerts  
**UI patterns:** Tremor Tracker / ProgressBar · HyperUI stats/badges · shadcnblocks KPI shells (pattern-copy only)  
**Rejected kits:** DaisyUI npm · React Bits · Cult Pro · 21st Financial packs  

Rubric axes (0–10): Cake · Cherry · Honesty · Speed · License/brand · Differentiation  

| Loop | Change | Sources | Cake | Cherry | Honesty | Diff | Notes |
|---|---|---|---:|---:|---:|---:|---|
| 1 | `TapePulseStrip` Appetite·Foreign·Book | Tremor CategoryBar spirit + HyperUI chips | 8 | 5 | 8 | 7 | Overview pulse ships |
| 2 | Foreign net + Δ + spark | Tremor Spark | 8 | 5 | 8 | 7 | Uses `market_daily_summary` |
| 3 | Book pressure bar + sample label | Tremor ProgressBar | 8 | 5 | 9 | 8 | Honest “not L2” |
| 4 | Appetite meter inside chip | existing koel | 8 | 5 | 8 | 7 | Keep Appetite naming |
| 5 | Tremor-style band tracker under pulse | Tremor Tracker | 9 | 5 | 8 | 8 | Session chronology |
| 6 | Nav **Context** link | HyperUI nav density | 8 | 5 | 8 | 8 | Not named Macro |
| 7 | `/context` page shell | shadcnblocks module grid | 8 | 6 | 8 | 8 | Separate from Overview |
| 8 | FX / Oil / Tourism / Food modules | HyperUI stats + spark ticker | 8 | 6 | 8 | 8 | Fail-soft empties |
| 9 | Source/as-of on every module | trust pattern | 8 | 6 | 9 | 9 | Beats opaque CSEPal |
| 10 | Sector bridge links | HyperUI chips | 8 | 6 | 8 | 9 | Arrivals→Hotels etc. |
| 11 | `GET /api/v1/market/tape` | API hygiene | 8 | 6 | 8 | 8 | Postgres only |
| 12 | Migration 027 + `macro_series` | schema | 8 | 6 | 9 | 8 | Flag-gated spine |
| 13 | CBSL FX adapter (XLSX) | official stats | 8 | 7 | 9 | 9 | LKR truth |
| 14 | EIA oil adapter | public domain | 8 | 7 | 9 | 9 | Attribution required |
| 15 | `macro-tick` CLI | ops | 8 | 7 | 8 | 8 | `--force` for smoke |
| 16 | MARKET Telegram: appetite/foreign/book | cherry | 8 | 9 | 8 | 10 | Tab-closed edge |
| 17 | MARKET Telegram: usdlkr/oil | cherry | 8 | 9 | 8 | 10 | Context→push |
| 18 | Alert labels + bot usage | dash/bot parity | 8 | 9 | 8 | 9 | Format hints |
| 19 | World/news honest deferral strip | fence | 8 | 9 | 10 | 9 | No fake tiles |
| 20 | Adversarial pass: no Macro clone / no scrape / NFA | KOEL edge | 9 | 9 | 10 | 10 | Pass |

**Composite after loop 20:** ≈ **8.6 / 10** on koel’s rubric (not CSEPal chart-count).

## CSEPal comparison (are we “better”?)

| Dimension | CSEPal Macro | koel after loops | Winner |
|---|---|---|---|
| Chart density / L2 depth history | Very high | Thin, honest | CSEPal (desk job) |
| Fear & Greed brand | Yes | Market Appetite (NFA) | koel (compliance) |
| Foreign + book on home | Buried in tabs | Overview pulse | **koel** |
| Telegram when tab closed | Weak / credits | MARKET regime alerts | **koel** |
| FX / oil attribution | Opaque | CBSL / EIA labeled | **koel** |
| Food / tourism SKU farm | Dense | Pressure index / monthly (gated) | CSEPal density / koel focus |
| Paywall | Credits + locks | Core free | **koel** |
| Competitor scrape | n/a | Forbidden | koel fence |

**Verdict:** We are **better on koel’s wedge** (clarity + Telegram + honesty). We are **not** denser than CSEPal’s Macro terminal — and should not try to be. Further loops should accrue real FX/oil history and wire regime evaluation into the poller send path, not add tab farms.

## Still open (next PRs)

1. Hook `evaluate_market_regime_rules` into poller/notify after each tick  
2. Complete CBSL/EIA ToS checklist rows → flip flags in prod  
3. SLTDA Excel + DCS food adapters when copyright confirmed  
4. Seed demo `macro_series` for preview environments  
5. Live screenshot pass on `*.agent.cvm.dev` once Neon URL available in shell  
