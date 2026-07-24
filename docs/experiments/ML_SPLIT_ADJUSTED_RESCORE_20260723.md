# Split-adjusted nested + cost re-score — 2026-07-23

Loop 1 lever 1 verification: regenerate nested survivors on
`price_adjustment=split` and re-run cost-engineering.

## Snapshot

- Path (VM): `/tmp/koel-live-final-snapshot-split`
- Method: clone of frozen hybrid snapshot + Neon `corporate_actions` sidecar
  (22 split/consolidation rows; no dividend factors)
- `bars_sha256`: `dc7de31d5c9ac46f17d878aee89676306da1959ff0b006badc7020a4a00f1da7` (unchanged)
- `corporate_actions_sha256`: `e6b29af6ab947517cd43bbc31ecc7ded24971168644c0fb6a637425131af356f`
- Adjustment applied at sample-build time (`koel/ml/adjustments.py`), not by rewriting bars

## Nested RankIC (relative / h1, CSE eval)

| Model | Unadjusted RankIC | Split-adjusted RankIC |
|---|---:|---:|
| `xgb_two_stage` | 0.2861 | 0.2837 |
| `hgb_two_stage` | 0.2816 | 0.2809 |
| `double_ensemble_native` | 0.2566 | 0.2554 |

Absolute `hgb_bagged` nested RankIC ≈ 0.2500 on split (was 0.2546 unadjusted).

## Cost-engineering gate (`persistence_exit_10_top_bottom_05` @112bps)

| Model | Unadj net@112 | Split net@112 | Survives? |
|---|---:|---:|---|
| **`double_ensemble_native`** | +0.36% | **+0.49%** | **Yes** |
| `xgb_two_stage` | +0.01% | +0.05% | Yes (thin) |
| `hgb_two_stage` | +0.03% | −0.13% | No |

**Policy gate: PASS** for DE persist on adjusted bars.

## Proposed Loop 0 shadow policy (review packet only)

- Proposed immutable ID: `shadow_policy_rank_de_persist_v1`
- Model: `double_ensemble_native`
- Portfolio construction: `persistence_exit_10_top_bottom_05`
- Cost assumption: 112 bps until corporate-action-adjusted live cost study
- **Not wired** into `live_shadow.py` in this change set — registration requires a
  dedicated relative+persistence emit path; do not replace existing absolute policies
- Still **not** user-facing: no `forecast_points`, Signal Board, or Telegram

## Honesty / contracts

- Selective 90% SuccessContract: still **not met**
- Daily top/bottom 10% post-cost without persistence: still negative
- Improve-loop 6×1000: exhausted (best RankIC 0.2746) — see `CPU_IMPROVE_6K_20260723.md`

## Artifacts (VM paths)

- `/tmp/cpu-exhaust-rel-h1-split/`
- `/tmp/cpu-exhaust-abs-h1-split/`
- `/tmp/cpu-cost-eng-split/cost_engineering_results.json`
- `/tmp/cpu-cost-eng-split/COMPARE_UNADJUSTED.md`
