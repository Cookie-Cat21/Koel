# CPU exhaust ladder — 2026-07-22

Status: **running**. GPU ladder retired for this push; the search
moves entirely onto CPU families + a 10 000-config LightGBM
calibration-only screen.

## Goal

Beat the current champion — native DoubleEnsemble RankIC **0.2526**
(BA 0.5763, MCC 0.1509, net spread @112 bps −0.69%) — under the same
nested protocol (3 folds, relative target, CSE eval domain, max flat
fraction 0.40, pooled 16 779 rows / 122 sessions). The strict
selective 90% precision/LCB contract remains the promotion bar and is
evaluated on every nested ensemble; it has not been met by any prior
corrected run.

## What this exhaust covers

1. **Family screen (fold 0)** of every CPU model in
   `koel/ml/cpu_challengers.CPU_EXHAUST_MODELS` (22 families):
   logistic, ridge, HGB variants (lmt/deep/bagged/weighted/domain/
   two-stage/regressor), XGB variants (lmt/domain/two-stage/regressor/
   rank-pairwise/rank-ndcg), LGB (lmt/domain/lambdarank), Qlib-parameter
   LightGBM, native DoubleEnsemble, and equal blends.
2. **Nested deep** (3 folds × seeds 0,1,2) for the top screen survivors
   plus the DoubleEnsemble champion.
3. **10 000 LightGBM configs** screened on **calibration RankIC only**;
   top-10 re-fit once and scored on the held-out test partition.

Harness: `python -m koel.ml.cpu_exhaust` (local) and
`.github/workflows/ml-cpu-exhaust.yml` (Actions, once the workflow is
on `main`).

## Snapshot

Frozen hybrid snapshot reused from the live/GPU work:

- `bars_sha256`: `dc7de31d5c9ac46f17d878aee89676306da1959ff0b006badc7020a4a00f1da7`
- `fundamentals_sha256`: `ce153d84cac292ad124478c18dc83467ddaeee2e9842dc12c276386ac06621a2`
- 917 087 rows / 292 symbols / 2000-01-03 → 2026-07-21

## Results

_Populated by the running exhaust; do not treat empty sections as
findings._

| Phase | Status | Notes |
|---|---|---|
| Family screen | pending | |
| Nested deep | pending | |
| 10k LGB screen | pending | |
| Contract met? | pending | |

## Safety

- `live_shadow.py` / policy IDs untouched.
- No `forecast_points` / Telegram writes.
- Hyperparameter selection is calibration-only; test is scored once for
  shortlisted winners.
