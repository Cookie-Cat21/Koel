# ML champion table

Updated: 2026-07-23

Source artifacts:

- `docs/experiments/CPU_EXHAUST_20260722.md`
- `docs/experiments/cpu_exhaust_rel_h1_summary.json`
- `docs/experiments/cpu_exhaust_abs_h1_summary.json`
- `docs/experiments/cpu_exhaust_rel_h1_lgb_10k.json`
- `docs/experiments/ML_COST_ENGINEERING_LOOP1_20260723.md`
- `docs/experiments/SELECTIVE_GATES_20260723.md`

## Current champions (score quality)

| Target / horizon | Status | Champion | RankIC | BA | MCC | daily net@112bps | Source |
|---|---|---|---:|---:|---:|---:|---|
| Relative / h1 | Nested RankIC champion | `xgb_two_stage` | 0.2861 | 0.5882 | 0.1771 | −0.78% | `cpu_exhaust_rel_h1_summary.json` |
| Absolute / h1 | Nested RankIC champion | `hgb_bagged` | 0.2546 | 0.5883 | 0.1812 | −1.32% | `cpu_exhaust_abs_h1_summary.json` |
| Relative / h1 | Prior baseline | DoubleEnsemble | 0.2526 | — | — | — | Qlib challenger report |
| Relative / h1 | Replicated baseline | `double_ensemble_native` | 0.2566 | 0.5777 | 0.1538 | −0.44% | `cpu_exhaust_rel_h1_summary.json` |

## Cost-engineering portfolio champion (offline, unadjusted bars)

Scores unchanged; only portfolio construction changes. Best variant:

| Model | Variant | RankIC | Gross | Net@112bps | Turnover | Sessions |
|---|---|---:|---:|---:|---:|---:|
| **`double_ensemble_native`** | `persistence_exit_10_top_bottom_05` | 0.2566 | 3.74% | **+0.36%** | 1.508 | 117 |
| `xgb_two_stage` | same | 0.2861 | 3.52% | +0.01% | 1.571 | 117 |
| `hgb_two_stage` | same | 0.2816 | 3.56% | +0.03% | 1.576 | 117 |

**First offline flip of net@112bps positive** under persistence + thinner books.
Caveat: bars are not yet split-adjusted in these shards — re-verify after
`--price-adjustment split` regenerates nested predictions (Loop 1 lever 1).

## Selective gates (90% contract)

**NOT MET** offline for `xgb_two_stage`, `hgb_two_stage`, or
`double_ensemble_native` under denser predeclared coverage grids.
Best near-miss: `xgb_two_stage` precision 0.770 / LCB 0.681 / 74 emits
(far below 500-emit and 0.90 LCB floors).

## Screen results that did not become champions

10 000 LightGBM relative/h1 best fold-0 test: `lgb_c34120c27d` RankIC
0.2640, net@112bps −0.73% — above DoubleEnsemble, below nested
`xgb_two_stage`.

## Promotion contract

**Contract: NOT MET for user-facing promotion.**

- Nested selective 90% SuccessContract: false (relative + absolute).
- Daily top/bottom 10% post-cost @112bps: negative for nested survivors.
- Persistence portfolio construction is **review-eligible for a new
  shadow policy ID only after** split-adjusted re-score confirms the
  +net result (cross-cutting: costs stay suspect until corporate actions).
- No `forecast_points`, Signal Board, or Telegram promotion from these
  results.

## Lever status (Loop 1 order)

| # | Lever | Status | Verdict |
|---|---|---|---|
| 1 | Corporate-action adjustment | **implemented** (`price_adjustment=split`) | Needs re-export + re-score of nested shards |
| 2 | Cost/turnover engineering | **first positive offline** | `persistence_exit_10_top_bottom_05` |
| 3 | Selective gate mining | exhausted for current scores | 90% unreachable offline |
| 4 | Ensembles/stacking | pending | next after adj re-score |
| 5 | New features | pending | |
| 6 | Horizons/targets | absolute/h1 done; h5 pending | |

## Next concrete actions

1. Re-export hybrid snapshot with `--price-adjustment split`.
2. Re-run nested survivors + cost-engineering variants on adjusted bars.
3. If +net survives adjustment → new immutable shadow policy ID
   (`shadow_policy_rank_de_persist_v1` or similar) for Loop 0 only.
4. Otherwise document exhaustion and keep RankIC champion as research score only.
