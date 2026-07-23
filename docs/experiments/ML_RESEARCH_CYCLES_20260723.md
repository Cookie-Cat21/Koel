# ML research cycles - 2026-07-23

## Cycle: CPU exhaust becomes the operating baseline

Status: research only; promotion blocked.

Evidence:

- `docs/experiments/CPU_EXHAUST_20260722.md`
- `docs/experiments/cpu_exhaust_rel_h1_summary.json`
- `docs/experiments/cpu_exhaust_abs_h1_summary.json`
- `docs/experiments/cpu_exhaust_rel_h1_lgb_10k.json`
- `docs/experiments/ML_CHAMPION_TABLE.md`
- `docs/factory/NORTH_STAR_LOOPS.md`

Decision:

- GPU challengers are retired from the active promotion path for now.
- CPU exhaust is the active research baseline because completed nested results
  landed a relative/h1 RankIC champion: `xgb_two_stage` at 0.2861, BA 0.5882,
  MCC 0.1771, net@112bps -0.78%.
- Absolute/h1 has a separate champion: `hgb_bagged` at RankIC 0.2546.
- The prior DoubleEnsemble baseline remains 0.2526; the replicated relative/h1
  `double_ensemble_native` result is 0.2566.
- The 10,000 LightGBM relative/h1 screen did not beat the nested
  `xgb_two_stage` champion.
- Contract is not met; post-cost @112 bps is negative across completed nested
  survivors.
- Improvement loops are in flight, but promotion remains blocked until the
  north-star gates are met.

Next levers, in order:

1. Corporate-action adjustment.
2. Cost/turnover.
3. Selective gates.
4. Ensembles.
5. Features.
6. Horizons.

Research only - not financial advice.


## Cycle update — levers 1–4 (2026-07-23, parallel)

| Lever | Result | Numbers |
|---|---|---|
| 1 Corporate-action adjustment | **Landed** | `price_adjustment=split` in snapshot/sample path; dividend data absent |
| 2 Cost/turnover | **First +net@112 offline** | `persistence_exit_10_top_bottom_05`: DE +0.36%, xgb2 +0.01%, hgb2 +0.03% (unadjusted bars) |
| 3 Selective gates | **Exhausted** | Best LCB 0.681 / 74 emits — 90% contract unreachable on current scores |
| 4 Ensembles/stacking | **Exhausted** | Best RankIC 0.2858 (−0.0003 vs champion); no cost improvement |

Next: re-score nested + cost variants on split-adjusted snapshot before any new shadow policy ID.
