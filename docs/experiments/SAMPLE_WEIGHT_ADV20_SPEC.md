# ADV20 sample-weight training lever

Goal-A research lever: `--sample-weight adv20` applies soft train-row weights
from point-in-time average daily volume. It does not remove samples, unlike
`--universe-filter liq_*`.

## Contract

- Default is frozen behavior: `--sample-weight ""`.
- `adv20` computes, for each training sample, the mean volume over the last
  up to 20 bars for the same symbol where `trade_date <= as_of`.
- Missing symbol history or missing usable volume is neutral: weight `1.0`.
- Raw weight is `log1p(adv20) / mean(log1p(adv20))` over non-missing rows.
- Final ADV weights are clipped to `[0.25, 4.0]`.
- The vector is passed only to model fits for the training partition; evaluation
  rows are never weighted and no rows are dropped.

## Scope

Implemented for `cpu_exhaust` and `distributed_worker` shared fit paths when
the underlying sklearn/XGBoost/LightGBM estimator accepts sample weights.
`live_shadow` is unchanged and continues to call the frozen default path.
