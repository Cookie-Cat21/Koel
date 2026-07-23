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


### Cycle — W3 relative/h5 nested complete (2026-07-23)

- Evidence: `CPU_EXHAUST_REL_H5_20260723.md`, `cpu_exhaust_rel_h5_summary.json`
- RankIC best: xgb_two_stage 0.1735; DE 0.1364; all daily L/S net@112 negative
- Selective: 0 calibration-safe emits (contract unmet)
- Cost best: DE persistence_exit_15 −0.56% net@112
- Verdict: h5 lever exhausted for current feature matrix without Goal A/B unlock
- Next: Feature Pack v1 nested (running); W2 liq_v1 filter nested queued

### Cycle — CSE-only nested killed (2026-07-23)

- Evidence: `CSE_ONLY_NESTED_20260723.md`, `cpu_exhaust_rel_h1_cse_summary.json`
- Snapshot: CSE-only export 2025-07-17 → 2026-07-22 (70k bars, 297 symbols)
- Result: all baseline trio models fail screen — insufficient history for nested split
- RankIC / selective / cost: **n/a** — no nested shards
- Verdict: CSE-only matrix **killed** for champion comparison; retain full matrix
- Champions unchanged; SuccessContract **still unmet**

### Cycle — W2 liq_v1 universe filter killed (2026-07-23)

- Evidence: `UNIVERSE_FILTER_LIQ_V1_NESTED_20260723.md`, `cpu_exhaust_rel_h1_liqv1_summary.json`
- Filter: ADV20 ≥1000, flat60 ≤0.40, min CSE sessions 20
- Sample collapse: 502908 → 32535 rows (−93.5%); nested sessions 117 → 78
- xgb/hgb: screen fail (insufficient train/test samples)
- DE partial RankIC: 0.1813 (2/3 folds) vs frozen 0.2566
- Selective: 0 emits (vs frozen xgb 74 / 0.770 prec)
- Cost best: DE min_hold_5 −0.40% net@112 (no persistence flip)
- Verdict: W2 kill criteria fired; preset rejected; fp+liq combo running
- Champions unchanged; SuccessContract **still unmet**

### Cycle — W1+W2 fp+liq combo killed (2026-07-23)

- Evidence: `FEATURE_PACK_LIQ_V1_NESTED_20260723.md`, `cpu_exhaust_rel_h1_fp_liq_summary.json`
- Matrix: feature_pack v1 + liq_v1 (same 32535-row universe)
- xgb/hgb: screen fail; DE partial RankIC 0.1779 (worse than liq_v1-only 0.1813)
- Selective: 0 emits; cost best DE min_hold_5 −0.27% net@112
- Verdict: combined matrix killed; no W5 merge; liq_v1 preset retired
- Champions unchanged; SuccessContract **still unmet**


### Cycle — W2 liq_v2 universe filter killed (2026-07-23)

- Evidence: `UNIVERSE_FILTER_LIQ_V2_NESTED_20260723.md`, `cpu_exhaust_rel_h1_liqv2_summary.json`
- Filter: ADV20 ≥100, flat60 ≤0.50, min CSE sessions 10
- Sample collapse: 636455 → 35328 rows (−94.4%); **below 100k floor**
- All trio nested complete (unlike liq_v1 screen fails)
- RankIC best: xgb 0.2136 vs frozen 0.2861
- Selective: 0 emits; cost best DE weekly −0.34% net@112
- Verdict: liq_v2 **killed**; recommend **liq_v3** (no ADV floor, flat≤0.40, CSE≥5)
- Champions unchanged; SuccessContract **still unmet**

### Cycle — W3 relative/h3 nested complete (2026-07-23)

- Evidence: `CPU_EXHAUST_REL_H3_20260723.md`, `cpu_exhaust_rel_h3_summary.json`
- RankIC best: xgb_two_stage 0.2285; hgb 0.2192; DE 0.1901
- Selective: hgb near-miss 91 emits / LCB 0.597 — contract unmet
- Cost best: DE weekly_5 +0.27% net@112 (h3 horizon only)
- Verdict: h3 lever **exhausted** (like h5); no Goal A/B unlock
- Champions unchanged; SuccessContract **still unmet**


## Status block — W0–W4 ledger (2026-07-23 evening)

**Promotion still blocked.** Champions unchanged: RankIC `xgb_two_stage` rel/h1
**0.2861**; cost DE persist split **+0.49%** @112; selective near-miss **0.770 /
0.681 / 74 emits**.

| Item | Verdict |
|---|---|
| W0 DE-persist shadow | Wired + report row; partial canary **14 legs** only — need **≥60 non-partial** sessions |
| W1 fpv1 nested | **Killed** — RankIC Δ **−0.0007**; no W1 materiality |
| W2 liq_v1 | **Killed** — 93% sample collapse; 0 selective emits |
| W2 liq_v2 | **Killed** — 94% sample collapse (35k rows); 0 selective emits |
| W2 liq_v3 | **In flight** — flat-only filter, no ADV floor |
| fp+liq combo | **Killed** with liq_v1 |
| W3 h5 | **Done, no unlock** — RankIC ~0.17; selective 0; cost negative |
| W3 h3 | **Done, no unlock** — RankIC 0.2285; selective 0; h3 cost +0.27% non-transferable |
| W4 CSE-only | **Killed** — ~1y history insufficient for nested splits |

**In flight / next:** liq_v3 nested; Goal A selective-90% chase on any improving
matrix; W5 only after new `matrix_id` materiality; W6 dossier **not** started —
**not truly exhausted** (E7–E8 open).

Research only — not financial advice.


### Cycle — h3 nested: RankIC down, weekly DE +net@112 (2026-07-23)

- Evidence: `CPU_EXHAUST_REL_H3_*`, `/tmp/cpu-post-rel-h3/`
- RankIC best 0.2285 < h1 champion — horizon does not beat h1 score quality
- Selective: unmet (hgb 91/0.681/LCB 0.597)
- Cost: DE `weekly_5_sessions_top_bottom_05` **+0.27%** net@112 (offline)
- Proposed shadow ID (unwired): `shadow_policy_rank_de_h3_weekly_v1`
- Next: wire h3 weekly shadow after h1 DE-persist receipts accumulate; liq_v3 in flight

