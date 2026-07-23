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

Next: Loop 0 shadow receipts for wired `shadow_policy_rank_de_persist_v1`;
features (lever 5) or horizons (lever 6). Split re-score **done** — see cycles
below.


## Cycle: cost engineering — +net@112 flip (unadjusted)

Status: offline portfolio construction only; **not promotion-ready**.

Evidence: `docs/experiments/ML_COST_ENGINEERING_LOOP1_20260723.md`

Decision:

- Scores unchanged; `persistence_exit_10_top_bottom_05` flips daily 10% net
  positive for three survivors on **unadjusted** nested shards.
- Best: `double_ensemble_native` +0.36% net@112bps (was −0.44% baseline);
  `xgb_two_stage` +0.01%; `hgb_two_stage` +0.03%.
- RankIC champion unchanged (`xgb_two_stage` 0.2861).
- Caveat: bars not yet split-adjusted — re-verify after lever 1 re-export.


## Cycle: selective gates — 90% contract fail

Status: **exhausted** for current nested scores.

Evidence: `docs/experiments/SELECTIVE_GATES_20260723.md`

Decision:

- No gate met `SuccessContract` (precision/LCB ≥0.90, emits ≥500, etc.).
- Best near-miss: `xgb_two_stage` precision 0.770 / LCB 0.681 / 74 emits.
- `double_ensemble_native`: zero emits under grid.
- 90% contract unchanged; do not weaken floors.


## Cycle: ensembles / stacking — fail

Status: **exhausted**; no challenger.

Evidence: `docs/experiments/ENSEMBLE_STACK_20260723.md`

Decision:

- Best blend `rank_average`: RankIC 0.2858 (−0.0003 vs champion 0.2861).
- Best blend persistence net@112bps −0.05% — no improvement vs champion
  (+0.01%) or DE (+0.36%).
- Retire survivor-blend path until new scores land from improve-loop or
  split-adjusted re-score.


## Cycle: improve-loop — exhausted (6×1000)

Status: **exhausted** — no breakthrough.

Evidence:

- `docs/experiments/CPU_IMPROVE_6K_20260723.md`
- `docs/experiments/cpu_improve_6k_harvest.json`

Decision:

- 6 cycles × 1 000 configs complete (LGB neighbourhood, XGB grid, blends,
  cost-shaped labels).
- Best test RankIC **0.2746** (`lgb_9faa353fb4`, cycle 0) < champion 0.2861.
- Best net@112 **−0.49%**; **no pos112** in any cycle.
- Retire improve-loop path; promotion remains blocked.


## Cycle: split-adjusted re-score — GATE PASS

Status: **verified** (Loop 1 lever 1 + 2 confirmation).

Evidence:

- `docs/experiments/ML_SPLIT_ADJUSTED_RESCORE_20260723.md`
- `docs/experiments/ML_SPLIT_COST_COMPARE_20260723.md`

Decision:

- Split-adjusted snapshot ready (22 corporate actions; no dividend factors).
- Nested re-score on adjusted bars: relative RankIC modest drift
  (`xgb_two_stage` 0.2861 → 0.2837; DE 0.2566 → 0.2554).
- Cost-engineering gate `persistence_exit_10_top_bottom_05` @112bps:
  DE unadj +0.36% → split **+0.49%** — **PASS**; xgb +0.05%; hgb flipped
  to −0.13%.
- Loop 0 policy ID `shadow_policy_rank_de_persist_v1` — offline reference
  +0.49%; wiring completed in later W0 cycle (see below).
- Selective 90% contract still **not met**; no `forecast_points` / Telegram /
  Signal Board promotion.


## Cycle: W0 wired + W1/W3 started (2026-07-23)

Status: Loop 0 shadow ledger extended; offline search continues; **promotion
still blocked**.

Evidence:

- `docs/factory/ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md`
- `koel/ml/live_shadow.py`, `docs/runbooks/ML_LIVE_SHADOW.md`
- `docs/experiments/FEATURE_PACK_V1_SPEC.md`, `koel/ml/feature_pack_v1.py`

Decision:

- **W0 done (wiring):** `shadow_policy_rank_de_persist_v1` registered in
  `live_shadow.py` — relative/h1 `double_ensemble_native` +
  `persistence_exit_10_top_bottom_05` book; emits book legs only to
  `forecast_outcomes` (gates `shadow_persist_book` /
  `shadow_partial_persist_book`). Still **not user-facing**; SuccessContract
  **still unmet**; prospective receipts not yet at ≥60 scored sessions.
- **W1 started (skeleton):** `feature_pack_v1` column manifest +
  stub helpers (`fp_adv20`, `fp_vol20`); not integrated into snapshot,
  dataset, or training.
- **W3 started:** relative/h5 nested baseline trio launched on current matrix
  (mirrors h1 exhaust protocol); no `cpu_exhaust_rel_h5_summary.json` yet.

Next: Loop 0 daily receipts for DE-persist shadow; complete W1 integration +
W3 h5 nested artifacts before W5 search.
