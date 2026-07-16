# CSE path history probe

**Date:** 2026-07-16  
**Endpoint:** `POST https://www.cse.lk/api/companyChartDataByStock`  
**Auth:** none (browser-like `Origin` / `Referer` headers)  
**Id mapping:** `stockId` = `companyInfoSummery.reqSymbolInfo.id` **or** `tradeSummary[].id` (same space). Not `securityId`.

## Period map (live)

Probed on `JKH.N0000` (stockId `297`), `COMB.N0000` (`208`), `SAMP.N0000` (`266`).

| `period` | Shape | Depth (observed) | Notes |
|---|---|---|---|
| `1` | Intraday ticks | Current session only | `o` usually null; `p`/`h`/`l`/`q`/`t` present |
| `2` | Daily bars | ~1 week (~5 sessions) | `o`/`c`/`pc` often null; use `p` as close |
| `3` | Daily bars | ~1 month (~21 sessions) | same |
| `4` | Daily bars | ~2 months (~42 sessions) | same |
| `5` | Daily bars | **~1 year** (~242 sessions, ~364 calendar days) | e.g. 2025-07-16 → 2026-07-15 UTC bar stamps |
| `≥6`, `0`, `-1` | Daily-ish | Falls back to ~1 week | Treat as useless |
| Strings (`1Y`, `MAX`, `daily`, …) | — | HTTP 400 | Do not use |

## Ceiling

Public JSON path history tops out at **~1 year of daily bars** via `period=5`.  
No multi-year / max history found. `POST /charts` (date-range) still **400**.  
`POST /chartData` remains index-scale (`symbol` ignored) — do not use for per-stock path.

`companyInfoSummery` exposes all-time hi/lo **scalars** (`allHiPrice` / `allLowPrice`) but not the series.

## Trade date convention

Daily bar timestamps are typically `18:30:00Z` (= midnight Asia/Colombo).  
Chime stores `trade_date` as the **Asia/Colombo calendar date** of `t`.

## Full-market cost (estimate)

One `period=5` call per symbol. At ~300–400 listed names and ≥0.35s polite gap → roughly **2–3 minutes** wall time for a full backfill. Prefer off-hours; flag-gated.

## Go / no-go

| Question | Answer |
|---|---|
| Can we backfill path for all companies? | **Yes** — ~1y daily via `period=5` |
| Multi-year from CSE today? | **No** |
| Longer history? | Forward `price_snapshots` + future daily rollups as Chime polls |

See also: `docs/endpoint_probe_report.md`, `docs/sample_responses/companyChartDataByStock.json`.
