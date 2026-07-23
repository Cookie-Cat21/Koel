# Post-process summary — rel-h1-liqv2

- generated_at: `2026-07-23T08:39:05.221534+00:00`
- nested_dir: `/tmp/cpu-exhaust-rel-h1-liqv2/nested`
- output_dir: `/tmp/cpu-post-rel-h1-liqv2`

## Selective gates (test partition)

| Model | Contract met | Precision | LCB | Emits | Symbols | Coverage |
|---|:---:|---:|---:|---:|---:|---:|
| xgb_two_stage | False | None | None | 0 | 0 | 0.0 |
| hgb_two_stage | False | None | None | 0 | 0 | 0.0 |
| double_ensemble_native | False | None | None | 0 | 0 | 0.0 |

## Cost engineering @112 bps

### Best net variant

- **double_ensemble_native** / `weekly_5_sessions_top_bottom_05`: net **−0.34%**
- gross: 0.52%
- mean one-way turnover: 0.385
- sessions: 117

### All models — top variant net@112

| Model | Best variant | Net | Gross | Turnover |
|---|---|---:|---:|---:|
| double_ensemble_native | weekly_5_sessions_top_bottom_05 | −0.34% | 0.52% | 0.385 |
| hgb_two_stage | min_hold_5_top_bottom_10 | −0.38% | 0.83% | 0.538 |
| xgb_two_stage | weekly_5_sessions_top_bottom_05 | −0.42% | 0.45% | 0.389 |

Research only — not financial advice.
