# Post-process summary — rel-h5

- generated_at: `2026-07-23T06:58:47.691831+00:00`
- nested_dir: `/tmp/cpu-exhaust-rel-h5/nested`
- output_dir: `/tmp/cpu-post-rel-h5`

## Selective gates (test partition)

| Model | Contract met | Precision | LCB | Emits | Symbols | Coverage |
|---|:---:|---:|---:|---:|---:|---:|
| xgb_two_stage | False | None | None | 0 | 0 | 0.0 |
| hgb_two_stage | False | None | None | 0 | 0 | 0.0 |
| double_ensemble_native | False | None | None | 0 | 0 | 0.0 |

## Cost engineering @112 bps

### Best net variant

- **double_ensemble_native** / `persistence_exit_15_top_bottom_10`: net **-0.56%**
- gross: 1.20%
- mean one-way turnover: 0.781
- sessions: 105

### All models — top variant net@112

| Model | Best variant | Net | Gross | Turnover |
|---|---|---:|---:|---:|
| double_ensemble_native | persistence_exit_15_top_bottom_10 | -0.56% | 1.20% | 0.781 |
| hgb_two_stage | persistence_exit_20_top_bottom_10 | -0.71% | 1.27% | 0.888 |
| xgb_two_stage | persistence_exit_20_top_bottom_10 | -1.01% | 0.94% | 0.871 |

Research only — not financial advice.
