# Post-process summary — abs-h5

- generated_at: `2026-07-23T10:40:21.904649+00:00`
- nested_dir: `/tmp/cpu-exhaust-abs-h5/nested`
- output_dir: `/tmp/cpu-post-abs-h5`

## Selective gates (test partition)

| Model | Contract met | Precision | LCB | Emits | Symbols | Coverage |
|---|:---:|---:|---:|---:|---:|---:|
| xgb_two_stage | False | None | None | 0 | 0 | 0.0 |
| hgb_two_stage | False | None | None | 0 | 0 | 0.0 |
| double_ensemble_native | False | None | None | 0 | 0 | 0.0 |

## Cost engineering @112 bps

### Best net variant

- **double_ensemble_native** / `persistence_exit_20_top_bottom_10`: net **-0.29%**
- gross: 1.05%
- mean one-way turnover: 0.597
- sessions: 105

### All models — top variant net@112

| Model | Best variant | Net | Gross | Turnover |
|---|---|---:|---:|---:|
| double_ensemble_native | persistence_exit_20_top_bottom_10 | -0.29% | 1.05% | 0.597 |
| hgb_two_stage | persistence_exit_20_top_bottom_10 | -0.88% | 0.77% | 0.737 |
| xgb_two_stage | persistence_exit_20_top_bottom_10 | -1.35% | 0.21% | 0.698 |

Research only — not financial advice.
