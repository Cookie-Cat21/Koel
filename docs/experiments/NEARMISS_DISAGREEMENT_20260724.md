# Near-miss trio + selective disagreement — fpv2 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet**.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v2` / relative / h1 |
| Models (shared nested) | `xgb_two_stage`, `xgb_lmt`, `hgb_lmt` (+ DE survivor) |
| Exhaust | `/tmp/cpu-exhaust-rel-h1-nearmiss` |
| Disagreement dirs | `/tmp/cpu-selective-disagree-nearmiss*` |

## Nested RankIC

| Model | RankIC | Δ vs frozen 0.2861 |
|---|---:|---:|
| `xgb_two_stage` | **0.2865** | +0.0004 |
| `xgb_lmt` | **0.2835** | -0.0026 |
| `hgb_lmt` | **0.2816** | -0.0045 |
| `double_ensemble_native` | **0.2553** | -0.0308 |

## Per-model selective (default grid)

| Model | Contract | Precision | LCB | Emits |
|---|:---:|---:|---:|---:|
| `double_ensemble_native` | False | None | None | 0 |
| `hgb_lmt` | False | 0.8518518518518519 | 0.775607052933559 | 81 |
| `xgb_lmt` | False | 0.8913043478260869 | 0.793055607035606 | 46 |
| `xgb_two_stage` | False | 0.7619047619047619 | 0.6875012389157168 | 105 |

## Selective disagreement variants

| Variant | Contract | Precision | LCB | Emits | Symbols | Coverage |
|---|:---:|---:|---:|---:|---:|---:|
| primary=xgb_lmt stdev | False | 0.8833333333333333 | 0.7980909188912355 | 60 | 38 | 0.0032939884710403516 |
| primary=xgb_lmt dense | False | 0.8833333333333333 | 0.7980909188912355 | 60 | 38 | 0.0032939884710403516 |
| primary=xgb_two_stage dense | False | 0.7619047619047619 | 0.6875012389157168 | 105 | 52 | 0.005764479824320615 |
| primary=xgb_lmt range | False | 0.8024691358024691 | 0.720449744902794 | 81 | 46 | 0.004446884435904475 |

**Verdict:** Best disagreement here is ~**0.883 / 0.798 / 60 emits** — high point
precision but fails emits (≥500), LCB (≥0.90), coverage (≥0.01), symbols (≥80),
and fold stability. Same class of near-miss as prior fpv2 disagreement
(0.779/0.693/77). **No Goal A unlock.**

Research only — not financial advice.
