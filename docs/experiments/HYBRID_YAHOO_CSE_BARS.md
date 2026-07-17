# Hybrid Yahoo + CSE daily bars

**Table:** `hybrid_daily_bars` (migration `022`)  
**CLI:** `python3 -m chime hybrid-backfill --force [--limit N]`  
**Flag:** `HYBRID_BACKFILL_ENABLED` (default `0`)

## What it is

A **second** history panel for ML/research:

| Layer | Source | Role |
|---|---|---|
| Recent | CSE `daily_bars` (`companyChartDataByStock`) | Truth — always wins on overlap |
| Older | Yahoo Finance `.CM` tickers via `yfinance` | Fill **before** each symbol’s first CSE bar |

Product spine (`daily_bars`, dash, Signal Board) is unchanged.

## Splice rules

1. Copy all CSE bars → `source='cse'`
2. Keep Yahoo bars only when `trade_date < first_cse_date`
3. Drop Yahoo on/after `YAHOO_STALE_CUTOFF` (default **2026-02-18** — feed went flat/wrong vs CSE)
4. Never overwrite a CSE date with Yahoo

Ticker map: `JKH.N0000` → `JKH-N0000.CM`

## Ops

```bash
pip install -e ".[hybrid]"   # yfinance + pandas
python3 -m chime.migrate
# Needs CSE path first:
python3 -m chime path-backfill --force --limit 50
python3 -m chime hybrid-backfill --force --limit 50
```

ML load:

```python
from chime.ml.dataset import load_symbol_bars
series = await load_symbol_bars(storage, hybrid=True)
```

## Compliance

- Yahoo has **no official API**; ToS discourages redistribution.
- Hybrid panel is **internal training / research** only — not shown as CSE truth on the dash.
- See `docs/THIRD_PARTY_DATA.md` (Tier D*).

## Smoke (this environment)

| | |
|---|---|
| Symbols | 200 ok (ASPI skipped) |
| Hybrid rows | **~917k** |
| Yahoo kept | ~870k (from **2000-01-03**) |
| CSE copied | ~47k (from **2025-07-18**) |

Research only — not financial advice.
