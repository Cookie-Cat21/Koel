# Post-process summary — rel-h3

- generated_at: `2026-07-23T08:39:04.970279+00:00`
- nested_dir: `/tmp/cpu-exhaust-rel-h3/nested`
- output_dir: `/tmp/cpu-post-rel-h3`

## Selective gates (test partition)

| Model | Contract met | Precision | LCB | Emits | Symbols | Coverage |
|---|:---:|---:|---:|---:|---:|---:|
| xgb_two_stage | False | None | None | 0 | 0 | 0.0 |
| hgb_two_stage | False | 0.681 | 0.597 | 91 | 37 | 0.0049 |
| double_ensemble_native | False | None | None | 0 | 0 | 0.0 |

## Cost engineering @112 bps

### Best net variant

- **double_ensemble_native** / `weekly_5_sessions_top_bottom_05`: net **+0.27%**
- gross: 1.03%
- mean one-way turnover: 0.340
- sessions: 111

### All models — top variant net@112

| Model | Best variant | Net | Gross | Turnover |
|---|---|---:|---:|---:|
| double_ensemble_native | weekly_5_sessions_top_bottom_05 | +0.27% | 1.03% | 0.340 |
| hgb_two_stage | min_hold_3_top_bottom_10 | −0.12% | 1.40% | 0.681 |
| xgb_two_stage | weekly_5_sessions_top_bottom_05 | +0.04% | 0.87% | 0.370 |

Research only — not financial advice.
