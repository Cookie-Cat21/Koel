# Near-miss LMT trio on fpv2+liq_v4 (2026-07-24)

## Setup

- Snapshot: `/tmp/koel-live-final-snapshot-split` (hybrid/split)
- Matrix: `--feature-pack v2 --universe-filter liq_v4`
- Models: `xgb_two_stage`, `xgb_lmt`, `hgb_lmt` (+ forced `double_ensemble_native`)
- Nested: 3 folds × seeds 0,1,2; `--skip-hyper`
- Output: `/tmp/cpu-exhaust-rel-h1-fpv2-liqv4-nearmiss`

## Nested RankIC vs frozen 0.2861

| Model | RankIC | Δ |
|---|---:|---:|
| xgb_two_stage | 0.2835 | −0.0026 |
| xgb_lmt | 0.2828 | −0.0033 |
| hgb_lmt | 0.2802 | −0.0059 |
| double_ensemble_native | 0.2532 | −0.0329 |

No RankIC materiality (+0.005). Cost spreads @112 remain negative on this nest.

## Selective

| Artifact | Model | Precision | LCB | Emits | Contract |
|---|---|---:|---:|---:|:---:|
| ultra-dense / gates | `xgb_lmt` | 0.8793 | 0.7916 | 58 | no |
| disagreement (primary xgb_lmt) | `xgb_lmt` | 0.8793 | 0.7916 | 58 | no |
| disagreement (primary xgb2) | `xgb_two_stage` | 0.7895 | 0.7131 | 95 | no |

Still short on emits (≥500), LCB (≥0.90), fold stability. SuccessContract **NOT MET**.

## Verdict

**Killed for Goal A unlock** on this matrix+trio. Proceed to 5-fold mass, fpv3+liq_v4, then wave2 skip-day + horizon-agree + rich metalabel.
