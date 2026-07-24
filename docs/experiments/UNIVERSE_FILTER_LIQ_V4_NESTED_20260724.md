# Universe filter liq_v4 — nested relative/h1 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet**.

## Run identity

| Field | Value |
|---|---|
| Matrix | `liq_v4` / relative / h1 / CSE |
| Filter | ADV20 ≥500; flat/CSE floors off |
| Samples | **439 190** / 502 908 baseline (**87.3%** retained) |
| Snapshot SHA | `2f7031a8f61a03a3…` |
| Models | baseline trio |
| Exhaust | `/tmp/cpu-exhaust-rel-h1-liqv4` |

## Nested RankIC vs frozen 0.2861

| Model | RankIC | Δ |
|---|---:|---:|
| `xgb_two_stage` | **0.2842** | -0.0019 |
| `hgb_two_stage` | **0.2822** | -0.0039 |
| `double_ensemble_native` | **0.2518** | -0.0343 |

## Selective

| Model | Contract | Precision | LCB | Emits |
|---|:---:|---:|---:|---:|
| `double_ensemble_native` | False | None | None | 0 |
| `hgb_two_stage` | False | 0.7525773195876289 | 0.6743113563916374 | 97 |
| `xgb_two_stage` | False | 0.8133333333333334 | 0.7289040028781751 | 75 |

Dense grid did not unlock (best still ~0.813 / 0.729 / 75).

## Cost @112

- best: `double_ensemble_native` / `persistence_exit_10_top_bottom_05` net **+0.54%**

## Materiality

| Gate | Result | Fired? |
|---|---|:---:|
| RankIC +0.005 | best Δ **-0.0019** | False |
| net@112 +0.10pp vs +0.49% | +0.54% | False |
| Selective emits 2× vs 74 | **97** | False |

**Verdict: killed on materiality** (sample floor **passed** — unlike v1–v3).
Next: `feature_pack_v2 + liq_v4` combo matrix.

Research only — not financial advice.
