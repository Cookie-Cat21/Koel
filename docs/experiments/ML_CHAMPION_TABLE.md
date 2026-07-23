# ML champion table

Updated: 2026-07-23 (Loop 1 verification complete; W0 DE-persist wired)

Source artifacts:

- `docs/experiments/CPU_EXHAUST_20260722.md`
- `docs/experiments/cpu_exhaust_rel_h1_summary.json`
- `docs/experiments/cpu_exhaust_abs_h1_summary.json`
- `docs/experiments/cpu_exhaust_rel_h1_lgb_10k.json`
- `docs/experiments/ML_COST_ENGINEERING_LOOP1_20260723.md`
- `docs/experiments/ML_SPLIT_ADJUSTED_RESCORE_20260723.md`
- `docs/experiments/ML_SPLIT_COST_COMPARE_20260723.md`
- `docs/experiments/CPU_IMPROVE_6K_20260723.md`
- `docs/experiments/cpu_improve_6k_harvest.json`
- `docs/experiments/SELECTIVE_GATES_20260723.md`
- `docs/experiments/ENSEMBLE_STACK_20260723.md`
- `docs/factory/ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md`
- `docs/runbooks/ML_LIVE_SHADOW.md`

## Current champions (score quality)

| Target / horizon | Status | Champion | RankIC | BA | MCC | daily net@112bps | Source |
|---|---|---|---:|---:|---:|---:|---|
| Relative / h1 | Nested RankIC champion | `xgb_two_stage` | 0.2861 | 0.5882 | 0.1771 | −0.78% | `cpu_exhaust_rel_h1_summary.json` |
| Absolute / h1 | Nested RankIC champion | `hgb_bagged` | 0.2546 | 0.5883 | 0.1812 | −1.32% | `cpu_exhaust_abs_h1_summary.json` |
| Relative / h1 | Prior baseline | DoubleEnsemble | 0.2526 | — | — | — | Qlib challenger report |
| Relative / h1 | Replicated baseline | `double_ensemble_native` | 0.2566 | 0.5777 | 0.1538 | −0.44% | `cpu_exhaust_rel_h1_summary.json` |

Split-adjusted nested RankIC (relative/h1): `xgb_two_stage` 0.2837, `hgb_two_stage`
0.2809, `double_ensemble_native` 0.2554 — see
`ML_SPLIT_ADJUSTED_RESCORE_20260723.md`.

## Cost-engineering portfolio champion (offline, split-adjusted bars)

Scores unchanged; only portfolio construction changes. Best variant on
**split-adjusted** nested shards:

| Model | Variant | RankIC (split) | Gross | Net@112bps | Turnover | Sessions |
|---|---|---:|---:|---:|---:|---:|
| **`double_ensemble_native`** | `persistence_exit_10_top_bottom_05` | 0.2554 | — | **+0.49%** | — | 117 |
| `xgb_two_stage` | same | 0.2837 | — | +0.05% | — | 117 |
| `hgb_two_stage` | same | 0.2809 | — | −0.13% | — | 117 |

**First offline flip of net@112bps positive** under persistence + thinner books;
**survives split adjustment** (unadjusted DE +0.36% → split +0.49%). See
`ML_COST_ENGINEERING_LOOP1_20260723.md`, `ML_SPLIT_ADJUSTED_RESCORE_20260723.md`,
`ML_SPLIT_COST_COMPARE_20260723.md`.

## Selective gates (90% contract)

**NOT MET** offline for `xgb_two_stage`, `hgb_two_stage`, or
`double_ensemble_native` under denser predeclared coverage grids.
Best near-miss: `xgb_two_stage` precision 0.770 / LCB 0.681 / 74 emits
(far below 500-emit and 0.90 LCB floors). See
`SELECTIVE_GATES_20260723.md`.

## Ensembles / stacking (survivor blends)

**Exhausted** — no gain vs RankIC champion or persistence net@112bps.
Best blend: `rank_average` RankIC 0.2858 (−0.0003 vs `xgb_two_stage`
0.2861); persistence net@112bps −0.05% (below `xgb_two_stage` +0.01% and
`double_ensemble_native` +0.36% unadjusted). See `ENSEMBLE_STACK_20260723.md`.

## Improve-loop 6×1000

**Exhausted** — no challenger. Best test RankIC **0.2746** (`lgb_9faa353fb4`,
cycle 0) < champion 0.2861; best net@112 −0.49%; **no pos112**. See
`CPU_IMPROVE_6K_20260723.md`, `cpu_improve_6k_harvest.json`.

## Screen results that did not become champions

10 000 LightGBM relative/h1 best fold-0 test: `lgb_c34120c27d` RankIC
0.2640, net@112bps −0.73% — above DoubleEnsemble, below nested
`xgb_two_stage`.

## Promotion contract

**Contract: NOT MET for user-facing promotion.**

- Nested selective 90% SuccessContract: false (relative + absolute).
- Daily top/bottom 10% post-cost @112bps: negative for nested survivors
  without persistence construction.
- Split-adjusted persistence +net@112 **confirmed** for
  `double_ensemble_native` / `persistence_exit_10_top_bottom_05` (+0.49%) —
  **review-eligible** Loop 0 shadow ledger only; not live promotion.
- Policy ID `shadow_policy_rank_de_persist_v1` — **wired for Loop 0 ledger**
  in `koel/ml/live_shadow.py` (`live_shadow` emits persistence book legs only
  to `forecast_outcomes`; gates `shadow_persist_book` /
  `shadow_partial_persist_book`). Still **not user-facing**; SuccessContract
  **still unmet** (selective 90%, global hard gates). See
  `docs/factory/ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md` §W0; runbook
  `docs/runbooks/ML_LIVE_SHADOW.md`. Prospective receipts pending (≥60 scored
  sessions not yet accumulated).
- No `forecast_points`, Signal Board, or Telegram promotion from these
  results.

## Lever status (Loop 1 order)

| # | Lever | Status | Verdict |
|---|---|---|---|
| 1 | Corporate-action adjustment | **done + verified** | Split snapshot (22 actions); nested + cost re-score complete |
| 2 | Cost/turnover engineering | **+net@112 verified (split-adjusted)** | DE `persistence_exit_10_top_bottom_05` +0.49%; xgb +0.05%; hgb −0.13% |
| 3 | Selective gate mining | **exhausted** | 90% contract unreachable offline |
| 4 | Ensembles/stacking | **exhausted** | best RankIC 0.2858 (−0.0003 vs champion); no net gain |
| 5 | New features | **started (W1 skeleton)** | `feature_pack_v1` spec + stub helpers; not in snapshot/train yet |
| 6 | Horizons/targets | absolute/h1 done; **h5 nested started (W3)** | no `cpu_exhaust_rel_h5_summary.json` yet |
| — | Improve-loop 6×1000 | **exhausted** | best RankIC 0.2746; no pos112 |

## Next concrete actions

1. Loop 0: accumulate prospective receipts for wired
   `shadow_policy_rank_de_persist_v1` (DE persist, split-adjusted +0.49%
   offline); monitor `live_shadow_report` — contract unchanged.
2. W1 feature pack + W3 h5 nested (parallel): only offline paths left toward
   global promotion gates — selective 90% still not met.
3. Keep RankIC champion (`xgb_two_stage` 0.2861) as research score only until
   contract + post-cost gates pass without persistence-only construction.
