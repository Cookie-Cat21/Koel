# Skip-day (--label-skip 1) on fpv2+liq_v4 (2026-07-24)

## Setup
- `--label-skip 1 --horizon 1 --feature-pack v2 --universe-filter liq_v4`
- Models: xgb_two_stage, xgb_lmt, hgb_lmt (+ forced DE)
- Output: `/tmp/cpu-exhaust-rel-skip1-fpv2-liqv4`

## Nested RankIC vs frozen 0.2861

| Model | RankIC | Δ |
|---|---:|---:|
| hgb_lmt | 0.0845 | −0.2016 |
| xgb_two_stage | 0.0837 | −0.2024 |
| xgb_lmt | 0.0822 | −0.2039 |
| double_ensemble_native | 0.0360 | −0.2501 |

## Verdict

**Killed.** Skip-day / execution-lag labels destroy cross-sectional RankIC on this
matrix (~0.08 vs 0.2861). Selective postprocess produced empty domain emits.
Do not promote; do not weaken SuccessContract. Horizon-agree (h1×h3) remains
the next wave2 lever.
