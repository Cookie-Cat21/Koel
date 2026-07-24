# Post-process summary — liqv1

- generated_at: `2026-07-23T07:36:30+00:00`
- nested_dir: `/tmp/cpu-exhaust-rel-h1-liqv1/nested`
- output_dir: `/tmp/cpu-post-rel-h1-liqv1`

## Selective gates (test partition)

| Model | Contract met | Precision | LCB | Emits | Symbols | Coverage |
|---|:---:|---:|---:|---:|---:|---:|
| xgb_two_stage | n/a | n/a | n/a | n/a | n/a | n/a |
| hgb_two_stage | n/a | n/a | n/a | n/a | n/a | n/a |
| double_ensemble_native | False | None | None | 0 | 0 | 0.0 |

## Cost engineering @112 bps

### Best net variant

- **double_ensemble_native** / `min_hold_5_top_bottom_10`: net **−0.40%**
- gross: 0.79%
- mean one-way turnover: 0.529
- sessions: 78

### All models — top variant net@112

| Model | Best variant | Net | Gross | Turnover |
|---|---|---:|---:|---:|
| double_ensemble_native | min_hold_5_top_bottom_10 | −0.40% | 0.79% | 0.529 |

Research only — not financial advice.
