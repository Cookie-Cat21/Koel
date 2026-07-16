# Always-on force-find ledger

**Baseline (locked):** `baseline_cs_lmt_bag` mean symbol hit = **0.5930**  
**Keep rule:** Δ ≥ **+0.005** under purged protocol.

## Cycles

| Lever | Mean symbol hit | Δ vs baseline | Keep? |
|---|---:|---:|:---:|
| baseline_cs_lmt_bag | 0.5930 | — | lock |
| events (disc/notice counts, ~4.9k disc / 1y) | 0.5927 | −0.0003 | **NO** |
| sector_rs (peer-relative ret 5/20) | 0.5938 | +0.0008 | **NO** |
| sector_rs + events | 0.5935 | +0.0005 | **NO** |
| + disc history to 2023 (~14.6k) + interactions | 0.5918 | −0.0012 | **NO** |

## Data ingested this wave

- `disclosures-backfill`: **273** symbols, **~14.6k** rows (2023-01 → 2026-07)
- `stocks.sector` already populated (prior wave)
- `index_snapshots`: only **intraday today** — not usable for walk-forward regime yet
- `market_notices` with symbol: **53** (sparse)

## Interpretation

Announcement **counts** alone do not move always-on direction hit. Likely need:

1. **Filing metrics / YoY numerics** from PDFs (not just “had a disclosure”)
2. **Daily ASPI/sector index history** for true market-regime features
3. Or accept that always-on stays high-50s and lean on **HPE (~90% when speaking)**

## Commands

```bash
python3 -m chime ml-always-on                 # baseline scoreboard
python3 -m chime ml-always-on --events        # vs baseline
python3 -m chime ml-always-on --sector-rs
python3 -m chime disclosures-backfill --force --limit 0
```

Research only — not financial advice.
