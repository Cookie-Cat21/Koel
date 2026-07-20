# High-Precision Emitter — 90% OOS precision (stress-tested)

**Status:** **TARGET MET** (selective system)  
**Tag:** `ml_hpe_p90_v1`  
**Report:** [ml_precision90_20260716T154908Z.md](ml_precision90_20260716T154908Z.md)  
**Config:** `koel/ml/hpe_p90_v1.json`

## What “90%” means here

| Claim | Result |
|---|---|
| Always-on board average 90% | **No** (~59% ceiling on path-only) |
| **When the system speaks**, OOS precision ≥ 90% | **Yes — 90.3%** |
| Enough emits for stats | **435** OOS emits · **82** symbols |
| Stress pack | **PASS** (time / symbol / sector jackknife / shuffle null) |

This is a **High-Precision Emitter (HPE)**: it stays silent most of the time (~0.5% coverage of sample-streams) and only publishes when locked gates fire.

## Winning gate

`pool|h1+h2+h3+h5+abs_dense@p90` — OR-pool of dense best-N@≥0.90 intersection gates across:

- panel horizons **1 / 2 / 3 / 5**
- **absolute** (non-panel) h=1 stream  

Each stream: LMT-bagged HGB classifier + `|score|` thr + `range_20d` (and often `vol_20d`) cuts.

## Stress pack (winning gate)

| Check | Value | OK |
|---|---|:---:|
| Early / late OOS precision | 0.885 / 0.927 | ✓ |
| Drop top-10 symbols | 0.883 | ✓ |
| Sector jackknife (large secs) | all ≥ 0.85 | ✓ |
| Shuffle null | ~0.49 | ✓ |

Fold table: 7/8 folds ≥ 0.85 (fold 2 ≈ 0.83 — monitored).

## How to run

```bash
# Re-validate on current daily_bars
python3 -m koel ml-precision90

# Serve gated forecasts (flag-gated)
export ML_HPE_ENABLED=1
python3 -m koel ml-hpe --force
```

Dash sparkline: uses `forecast_points` for `ml_hpe_p90_v1` when present; most symbols will have **no** overlay (silence = no high-precision signal).

## Honest limits

- Not a promise of future 90% — OOS on ~1y CSE path under purge/embargo.
- Coverage is thin by design; widening it without new data drops precision (N≥200 single-stream ceiling was ~84–86%).
- Filings still empty — further coverage at 90% likely needs fundamentals.

Research only — not financial advice.
