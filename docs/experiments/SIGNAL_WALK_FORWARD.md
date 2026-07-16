# Signal Board — walk-forward forecast eval

**Date:** 2026-07-16  
**Model:** `path_v0_fc` / naive mean of last 5 daily returns × 5 horizons  
**Command:** `python3 -m chime eval-signals --limit 50`

## Results (50 symbols, Neon `daily_bars`)

| Metric | Value |
|---|---|
| Symbols used | 50 |
| Origins | 2,032 |
| Direction hits / total | 900 / 1,904 |
| **Hit rate** | **0.473** |
| MAE (price units) | 11.93 |
| Horizon | 5 |

## Interpretation

Direction hit rate is **≈ chance (0.5)**. The naive path forecast is **not** an edge signal. It remains available as a **research overlay** (dashed sparkline) with NFA labeling — not a price target, not advice.

`path_v1` research **scores** (momentum / vol / liquidity / filing YoY / peer RS when sector present) are separate from this forecast and are explainable factor blends, not ML price oracles.

## Next kill / improve criteria

- Promote a new forecast model only if walk-forward hit rate ≥ 0.55 on ≥100 symbols with leakage checklist.
- Until then: keep overlay opt-in; default sparkline = realtime only.
