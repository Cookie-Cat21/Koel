# CPU exhaust — relative / h5 (split-adjusted) — 2026-07-23

Research only — not financial advice.

- Snapshot: split-adjusted hybrid (`price_adjustment=split`)
- Samples: nested deep on `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native`
- `any_beats_baseline`: `False`

## Nested RankIC

| Model | RankIC | Sessions | Rows | net@112 (daily L/S) |
|---|---:|---:|---:|---:|
| `hgb_two_stage` | 0.1729 | 105 | 17703 | -1.71% |
| `xgb_two_stage` | 0.1735 | 105 | 17703 | -1.65% |
| `double_ensemble_native` | 0.1364 | 105 | 17703 | -1.28% |

## Post-process (selective + cost)

See `CPU_EXHAUST_REL_H5_POST_20260723.md`.

### Headline
- Selective 90%: **not met** (0 emits under calibration-safe gates for all three models).
- Best cost variant offline: DE `persistence_exit_15_top_bottom_10` **−0.56%** net@112 (still negative).

Horizon h5 does **not** clear Goal A or Goal B cost gate on this matrix.
