# Signal Board — walk-forward forecast eval

**Updated:** 2026-07-16  
**Commands:** `python3 -m koel eval-signals --limit 50`

## Models tried

| Model | Hit rate | MAE | Notes |
|---|---:|---:|---|
| `path_v0_fc` (mean of last 5 daily rets) | 0.473 | 11.93 | Baseline |
| `path_v2_fc` (0.6×5d + 0.4×20d, flatten if \|drift\|&lt;0.2%) | 0.461 | 10.62 | MAE↓ but hit rate still ≈ chance |

## Interpretation

Direction hit rate remains **≈ coin flip**. Per plan kill criteria (&lt; 0.55), **do not promote** the forecast as an edge signal. Keep sparkline overlay **opt-in** with NFA copy (“model estimate”).

Research **scores** (`path_v2`) are a separate product surface — transparent factor blend, not this forecast.

## Promote criteria (unchanged)

- Walk-forward hit rate ≥ **0.55** on ≥100 symbols  
- Leakage checklist signed off  
- Until then: realtime sparkline default; forecast checkbox only
