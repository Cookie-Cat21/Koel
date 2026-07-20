# ML model summary (CSE Signal Board)

**Status:** Experiment **GO** by gates; production write path behind  
`ML_FORECAST_ENABLED` (default **0**).  
**Artifact tag:** `ml_hgb_ret_v1`  
**Report:** [ml_walkforward_20260716T135132Z.md](ml_walkforward_20260716T135132Z.md)

## What the model is

| Item | Choice |
|---|---|
| Family | `HistGradientBoostingRegressor` (scikit-learn) |
| Task | Predict **forward return** at horizons 1…5 trading days |
| Features | Path-only vector (`ret_1/5/20/60`, vol, liquidity, spike, range, regime, turnover, gaps, log price) |
| Train regimen | Fit on all `daily_bars` samples with ≥60 days history (retrain each `ml-forecast` run) |
| Output | `forecast_points.yhat` = last close × (1 + predicted return), capped ±20% per horizon |
| Dash | Same sparkline toggle; shows latest `forecast_points` (ML when flag-written) |

Also evaluated (not the serve default): **L2 logistic** for direction — best 1d hit rate in the experiment.

## Walk-forward accuracy (full Neon board)

Universe: **273** symbols · **64,400** daily bars · ~2025-07-17 → 2026-07-16.

| Model | Horizon | Hit rate | Spearman IC | Origins |
|---|---:|---:|---:|---:|
| Logistic (B1) | 1d | **0.586** | 0.082 | 12,957 |
| HGB classifier (M1) | 1d | **0.563** | 0.119 | 12,957 |
| HGB regressor (M2) | 1d | 0.537 | **0.156** | 12,957 |
| Logistic (B1) | 5d | **0.573** | 0.097 | 9,981 |
| HGB classifier (M1) | 5d | **0.561** | 0.131 | 9,981 |
| HGB regressor (M2) | 5d | 0.524 | 0.077 | 9,981 |
| Naive path forecast (B0) | 5d | 0.443 | — | 9,500 |

**Gates:** hit rate ≥ 0.55 **or** IC ≥ 0.03 → **GO**.  
**Naive overlay** remains weaker; ML is preferred when enabled.

## How to enable

```bash
pip install -e ".[ml]"
export ML_FORECAST_ENABLED=1
python3 -m koel ml-forecast --force          # or score-signals with flag on
```

Dash: open a symbol → **Show forecast** (NFA: research estimate, not advice).

## Hardened re-check (purge · RankIC · gate)

See [ML_HARDENED_SUMMARY.md](ML_HARDENED_SUMMARY.md) and
`ml_hardened_20260716T145857Z.md`. Under purge/embargo + 7–8 folds:

- 1d purged hit still **~0.56–0.57** (did not collapse to chance)
- Mean daily **RankIC ~0.21–0.24** (panel HGB best)
- Confidence gate: panel HGB **~66% hit on ~22% of samples** at \|P−0.5\|≥0.15

```bash
python3 -m koel ml-harden --horizons 1,5
```

## Caveats

- Only **~1 year** of CSE path — hardened folds help, still not multi-year proof.
- Path features only in v1 serve (no live filing/notice join in the predictor).
- Retrain-every-run is simple/ops-friendly; no model registry yet.
- Always **not financial advice**.

## Ops knobs

| Env | Default | Meaning |
|---|---|---|
| `ML_FORECAST_ENABLED` | `0` | score-signals uses ML forecasts when `1` |
| `ml-forecast --force` | — | Write forecasts even if env flag off |
