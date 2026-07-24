# CPU exhaust — relative / h3 (split-adjusted) — 2026-07-23

Research only — not financial advice.

- Snapshot: split-adjusted hybrid (`price_adjustment=split`, sha `fc4d730527d4821f…`)
- Samples: **636 455** (full matrix, no universe filter)
- Models: `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native`
- `any_beats_baseline`: `False`
- `nested_contract_met`: `False`

## Nested RankIC

| Model | RankIC | Sessions | Rows | net@112 (daily L/S) |
|---|---:|---:|---:|---:|
| **`xgb_two_stage`** | **0.2285** | 111 | 18 463 | −0.71% |
| `hgb_two_stage` | 0.2192 | 111 | 18 463 | −1.07% |
| `double_ensemble_native` | 0.1901 | 111 | 18 463 | −0.44% |

Frozen relative/h1 champion: `xgb_two_stage` **0.2861** — h3 best is **−0.0576**
below h1.

## Post-process (selective + cost)

See `CPU_EXHAUST_REL_H3_POST_20260723.md`.

### Headline

- Selective 90%: **not met** (0 emits for xgb/DE; hgb near-miss 91 emits / LCB
  0.597 / prec 0.681 — still below 500-emit and 0.90 LCB floors).
- Best cost variant offline: DE `weekly_5_sessions_top_bottom_05` **+0.27%**
  net@112 on h3 horizon — does not transfer to h1 champion path.

Horizon h3 does **not** clear Goal A or Goal B on this matrix. Lever **exhausted**
(analogous to h5).

Artifacts: `cpu_exhaust_rel_h3_summary.json`, exhaust dir
`/tmp/cpu-exhaust-rel-h3`, post-process `/tmp/cpu-post-rel-h3`.
