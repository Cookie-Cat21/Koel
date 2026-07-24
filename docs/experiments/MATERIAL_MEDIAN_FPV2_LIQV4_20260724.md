# material_median labels on fpv2+liq_v4 (2026-07-24)

## Setup
- `--label-policy material_median` (keep |y_ret| ≥ same-day median before demean)
- `--feature-pack v2 --universe-filter liq_v4`
- samples: 218699 (vs ~439k unfiltered)
- Output: `/tmp/cpu-exhaust-rel-matmed-fpv2-liqv4`

## Nested RankIC vs frozen 0.2861

| Model | RankIC | Δ |
|---|---:|---:|
| xgb_two_stage | 0.3017 | +0.0156 |
| hgb_lmt | 0.2938 | +0.0077 |
| xgb_lmt | 0.3015 | +0.0154 |
| double_ensemble_native | 0.2848 | -0.0013 |

**RankIC materiality (+0.005): MET** (best Δ **+0.0156**). W5 hyper unlock on this matrix.

## Selective (wave3)

| Artifact | Best | Prec | LCB | Emits | Contract |
|---|---|---:|---:|---:|:---:|
| ultra-dense | hgb_lmt | 0.8017 | 0.7553 | 232 | no |
| disagreement | xgb_lmt | 0.8264 | 0.7628 | 121 | no |

SuccessContract **NOT MET** (need ≥0.90 prec/LCB, ≥500 emits, fold stability).
This is a **new label policy / matrix** — not a silent rewrite of the frozen h1 label.

## Verdict
RankIC unlocked for W5; selective Goal A still open. No promotion.
