# Goal A — skip-day labels + horizon-agreement selective (2026-07-24)

## Why

Same-matrix RankIC ~0.28 and model-disagreement selective peaked near
**0.883 / 0.798 / 60 emits** — still short of SuccessContract (precision & LCB
≥0.90, ≥500 emits, fold stability, …). Open→close labels are infeasible on CSE
(open coverage ~0). Next levers are **new label** and **new gate**, not another
family sweep.

## Changes (research only)

1. **`--label-skip N`** on `koel.ml.cpu_exhaust` / `build_samples` / `labels_at`
   - Features stay at `as_of`; return measured from `as_of+N` → `as_of+N+horizon`.
   - Nested embargo uses `max(5, horizon + label_skip)`.
   - Default `0` preserves the frozen champion contract.
2. **`koel.ml.selective_horizon_agree`**
   - Align h1×h3 nested shards; keep same-sign scores; mine dense selective
     gates on calibration only; coverage denominator = primary test rows.

## Queue

- Wave 1 (`/tmp/koel-goal-a-continue.sh`): fpv2+liq_v4 near-miss → 5-fold → fpv3+liq_v4
- Wave 2 (`scripts/ml_goal_a_wave2.sh`): skip-day (`--label-skip 1`) nest + h3 nest
  + horizon-agree on fpv2+liq_v4 near-miss carriers

## Hard constraints

- SuccessContract **not weakened**.
- No `forecast_points` / Telegram / promotion.
- Historical DE replay (`--as-of`, policy `…_hist_v1`) is **not** E7-eligible.

## Status

In flight at authoring time. Harvest artifacts:

- `/tmp/goal-a-continue-harvest.md`
- `/tmp/goal-a-wave2-harvest.md`
