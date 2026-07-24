# ML champion table

Updated: 2026-07-24 (advw nested exhausted; abs/h1 split + fpv2+advw in flight)

Source artifacts:

- `docs/experiments/CPU_EXHAUST_20260722.md`
- `docs/experiments/cpu_exhaust_rel_h1_summary.json`
- `docs/experiments/cpu_exhaust_rel_h1_fpv1_summary.json`
- `docs/experiments/FEATURE_PACK_V1_NESTED_20260723.md`
- `docs/experiments/CSE_ONLY_NESTED_20260723.md`
- `docs/experiments/cpu_exhaust_rel_h1_cse_summary.json`
- `docs/experiments/UNIVERSE_FILTER_LIQ_V1_NESTED_20260723.md`
- `docs/experiments/cpu_exhaust_rel_h1_liqv1_summary.json`
- `docs/experiments/FEATURE_PACK_LIQ_V1_NESTED_20260723.md`
- `docs/experiments/cpu_exhaust_rel_h1_fp_liq_summary.json`
- `docs/experiments/cpu_exhaust_abs_h1_summary.json`
- `docs/experiments/cpu_exhaust_rel_h1_lgb_10k.json`
- `docs/experiments/ML_COST_ENGINEERING_LOOP1_20260723.md`
- `docs/experiments/ML_SPLIT_ADJUSTED_RESCORE_20260723.md`
- `docs/experiments/ML_SPLIT_COST_COMPARE_20260723.md`
- `docs/experiments/CPU_IMPROVE_6K_20260723.md`
- `docs/experiments/cpu_improve_6k_harvest.json`
- `docs/experiments/SELECTIVE_GATES_20260723.md`
- `docs/experiments/ENSEMBLE_STACK_20260723.md`
- `docs/experiments/UNIVERSE_FILTER_LIQ_V2_NESTED_20260723.md`
- `docs/experiments/cpu_exhaust_rel_h1_liqv2_summary.json`
- `docs/experiments/CPU_EXHAUST_REL_H3_20260723.md`
- `docs/experiments/cpu_exhaust_rel_h3_summary.json`
- `docs/experiments/CPU_EXHAUST_ABS_H3_20260724.md`
- `docs/experiments/cpu_w5_fpv2_2k_summary.json`
- `docs/experiments/FEATURE_PACK_V2_NESTED_20260724.md`
- `docs/experiments/cpu_exhaust_rel_h1_fpv2_summary.json`
- `docs/experiments/SAMPLE_WEIGHT_ADV20_NESTED_20260724.md`
- `docs/experiments/cpu_exhaust_rel_h1_advw_summary.json`
- `docs/experiments/SELECTIVE_DENSE_FPV2_20260724.md`
- `docs/experiments/SELECTIVE_DISAGREEMENT_20260724.md`
- `docs/experiments/UNIVERSE_FILTER_LIQ_V3_SPEC.md`
- `docs/experiments/UNIVERSE_FILTER_LIQ_V3_NESTED_20260723.md`
- `docs/experiments/cpu_exhaust_rel_h1_liqv3_summary.json`
- `docs/experiments/SELECTIVE_GATES_H3_HGB_WIDE_20260723.md`
- `docs/experiments/selective_gates_h3_hgb_wide_20260723.json`
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
- Policy ID `shadow_policy_rank_de_h3_weekly_v1` — **wired for Loop 0 ledger**
  in `koel/ml/live_shadow.py` (`horizon_days=3`, gates
  `shadow_h3_weekly_book` / `shadow_partial_h3_weekly_book`). Weekly cadence:
  rebuild when `session_index % 5 == 0`, otherwise re-emit prior book sides
  with incremented ages. Offline h3 reference +0.27% net@112bps; still not
  user-facing and **does not** satisfy the selective 90% SuccessContract.
- No `forecast_points`, Signal Board, or Telegram promotion from these
  results.

## Lever status (Loop 1 order)

| # | Lever | Status | Verdict |
|---|---|---|---|
| 1 | Corporate-action adjustment | **done + verified** | Split snapshot (22 actions); nested + cost re-score complete |
| 2 | Cost/turnover engineering | **+net@112 verified (split-adjusted)** | DE `persistence_exit_10_top_bottom_05` +0.49%; xgb +0.05%; hgb −0.13% |
| 3 | Selective gate mining | **exhausted** | 90% contract unreachable offline |
| 4 | Ensembles/stacking | **exhausted** | best RankIC 0.2858 (−0.0003 vs champion); no net gain |
| 5 | New features | **fpv1 + fpv2 nested done — no materiality** | fpv1 Δ −0.0007; fpv2 xgb +0.0004; W1 thresholds **not fired** |
| 5c | Sample weight adv20 | **exhausted** | xgb +0.0001 RankIC; selective regresses (xgb 0 emits); DE +0.45% vs +0.49% |
| 5e | fpv2 + adv20 combo | **exhausted** | xgb +0.0006 RankIC; selective LCB 0.685; DE +0.59% borderline (`FEATURE_PACK_V2_ADV20_NESTED_20260724.md`) |
| 5f | fpv2 extra (bagged/LMT/deep) | **exhausted** | best `xgb_lmt` 0.2835 (−0.0026 vs champion); selective 46 emits / LCB 0.793 (`FEATURE_PACK_V2_EXTRA_NESTED_20260724.md`) |
| 5g | Ranking models (LTR) | **exhausted** | best `lgb_lambdarank` 0.2647; 0 selective emits (`RANKING_MODELS_NESTED_20260724.md`) |
| 5h | DE blends | **exhausted** | best `blend_de_lgb` 0.2557; net +0.58% cost-only; 0 selective emits (`BLEND_MODELS_NESTED_20260724.md`) |
| 5i | Simple models (ridge/logit/reg) | **exhausted** | best `xgb_regressor` 0.2625 (−0.0236); selective 0; cost +0.51% (`SIMPLE_MODELS_NESTED_20260724.md`) |
| 5d | Selective denser + disagreement (fpv2) | **exhausted** | best 0.779/0.693/77 emits; contract **false** |
| 5b | Universe filter W2 | **exhausted/killed — universe collapse** | v1 −93.5%; v2 35,328 rows; v3 35,377 rows; 0 selective emits; flat-only filter still <100k |
| 6 | Horizons/targets | absolute/h1 done; abs/h1 split selective **exhausted (0 emits)**; rel/h3 + abs/h3 + h5 exhausted | rel/h3 0.2285; **abs/h3 0.2061**; h5 0.1735; no Goal A/B unlock |
| 6b | abs/h1 split selective denser | **exhausted** | 0 emits all models; denser grid 0.001–0.10 (`CPU_EXHAUST_ABS_H1_SPLIT_20260724.md`) |
| — | Improve-loop 6×1000 | **exhausted** | best RankIC 0.2746; no pos112 |

## Research cycle — W1 feature pack v1 (2026-07-23)

Nested relative/h1 with `--feature-pack v1` on split-adjusted snapshot
(`FEATURE_PACK_V1_NESTED_20260723.md`, `cpu_exhaust_rel_h1_fpv1_summary.json`).

| Model | Frozen RankIC | fpv1 RankIC | Δ | Frozen DE-persist net@112 | fpv1 best net@112 |
|---|---:|---:|---:|---:|---:|
| `xgb_two_stage` | 0.2861 | 0.2854 | −0.0007 | — | −0.06% |
| `hgb_two_stage` | 0.2816 | 0.2809 | −0.0007 | — | −0.07% |
| `double_ensemble_native` | 0.2566 | 0.2510 | −0.0056 | +0.49% | +0.53% |

**W1 materiality (master plan): all NOT fired.**

- RankIC +0.005: best Δ **−0.0007** (xgb).
- net@112 +0.10 pp: best Δ **+0.04 pp** (DE persist vs frozen +0.49%).
- Selective emits 2×: xgb **94 vs 74** (1.27×), hgb **94 vs 86** (1.09×).

**Champions retained:** RankIC `xgb_two_stage` 0.2861; cost DE persist +0.49%.
SuccessContract **still unmet**. Next W1 slice: fp+liq combo exhaust (running).

## W2 universe filter liq_v1 (2026-07-23) — killed

Nested relative/h1 with `--universe-filter liq_v1` (`UNIVERSE_FILTER_LIQ_V1_NESTED_20260723.md`).

| Model | Frozen RankIC | liq_v1 RankIC | Selective (best) | Best net@112 |
|---|---:|---:|---|---:|
| `xgb_two_stage` | 0.2861 | n/a (fail) | frozen 74 / 0.770 | frozen −0.78% daily L/S |
| `double_ensemble_native` | 0.2566 | 0.1813* | 0 emits | −0.40% |

\*Partial nested (2/3 folds). Filter removes 93.5% of samples; W2 kill criteria fired.
fp+liq combo (DE 0.1779) equally killed — see `FEATURE_PACK_LIQ_V1_NESTED_20260723.md`.
Champions unchanged.

## W1+W2 fp+liq combo (2026-07-23) — killed

Combined `--feature-pack v1 --universe-filter liq_v1`: same 32 535-row ceiling;
xgb/hgb fail; DE RankIC 0.1779; 0 selective emits; best net@112 −0.27%.
No synergy vs single levers. See `FEATURE_PACK_LIQ_V1_NESTED_20260723.md`.

## CSE-only nested (2026-07-23) — killed

Relative/h1 baseline trio on Postgres CSE-only export (`dataset=cse`,
2025-07-17 → 2026-07-22): **all models failed** family screen —
`not enough history for requested nested split`. No RankIC, selective, or
cost numbers. See `CSE_ONLY_NESTED_20260723.md`. Champions unchanged.

## W2 universe filter liq_v2 (2026-07-23) — killed

Nested relative/h1 with `--universe-filter liq_v2` (`UNIVERSE_FILTER_LIQ_V2_NESTED_20260723.md`).

| Model | Frozen RankIC | liq_v2 RankIC | Selective (best) | Best net@112 |
|---|---:|---:|---|---:|
| `xgb_two_stage` | 0.2861 | 0.2136 | 0 emits | −0.42% |
| `double_ensemble_native` | 0.2566 | 0.1783 | 0 emits | −0.34% |

Filter removes **94.4%** of samples (636 455 → 35 328); below 100 k floor. W2 kill
criteria fired. Next: `liq_v3` flat-only manifest (`UNIVERSE_FILTER_LIQ_V3_SPEC.md`).
Champions unchanged.

## W2 universe filter liq_v3 (2026-07-23) — exhausted

Nested relative/h1 with `--universe-filter liq_v3`
(`UNIVERSE_FILTER_LIQ_V3_NESTED_20260723.md`).

| Model | Frozen RankIC | liq_v3 RankIC | Selective | net@112 |
|---|---:|---:|---|---:|
| `xgb_two_stage` | 0.2861 | 0.2227 | 0 emits | −1.49% |
| `hgb_two_stage` | 0.2816 | 0.2138 | 0 emits | −1.76% |
| `double_ensemble_native` | 0.2566 | 0.1785 | 0 emits | −1.88% |

Filter keeps only **35,377** samples (<100k), essentially the same collapse as
liq_v2. ADV removal did not recover depth; **flat_fraction alone collapses hybrid
history** for this snapshot. W2 universe-filter lever is **exhausted/killed**.
Champions unchanged; SuccessContract **still unmet**.

## Horizon h3 (2026-07-23) — exhausted

Relative/h3 nested on split snapshot: RankIC champ `xgb_two_stage` **0.2285**
(−0.0576 vs h1 0.2861). Selective: hgb near-miss 91 emits / LCB 0.597 — **contract
unmet**. Best cost: DE `weekly_5_sessions_top_bottom_05` **+0.27%** net@112 on h3
horizon only. See `CPU_EXHAUST_REL_H3_20260723.md`.

Follow-up h3 hgb wide absolute-score selective grid reproduced the same no-unlock
near-miss: 91 emits / precision 0.681 / LCB 0.597 / coverage 0.00493, contract
false. See `SELECTIVE_GATES_H3_HGB_WIDE_20260723.md`.

## Next concrete actions

1. Loop 0: accumulate prospective receipts for wired
   `shadow_policy_rank_de_persist_v1` (DE persist, split-adjusted +0.49%
   offline); monitor `live_shadow_report` — contract unchanged.
2. Keep RankIC champion (`xgb_two_stage` 0.2861) as research score only until
   contract + post-cost gates pass without persistence-only construction.


## Horizon h3 cost find (2026-07-23)

Offline nested relative/**h3** (split snapshot): RankIC still below h1 champion
(`xgb_two_stage` 0.2285 vs 0.2861). Selective 90% **not met** (hgb near-miss
91 emits / LCB 0.597).

**New cost-positive construction on h3 scores:**

| Model | Variant | Net@112 | Gross | Turnover | Sessions |
|---|---|---:|---:|---:|---:|
| `double_ensemble_native` | `weekly_5_sessions_top_bottom_05` | **+0.27%** | 1.03% | 0.340 | 111 |
| `xgb_two_stage` | same | +0.04% | 0.87% | 0.370 | 111 |

Review-only Loop 0 ID now wired:
`shadow_policy_rank_de_h3_weekly_v1` — relative/h3 DE + weekly 5-session
top/bottom 5% book. It does **not** replace h1 DE-persist (+0.49%) or clear
selective 90%. See `CPU_EXHAUST_REL_H3_20260723.md`,
`ML_H3_WEEKLY_COST_20260723.md`, and `docs/runbooks/ML_LIVE_SHADOW.md`.

## Absolute/h5 (2026-07-23)

Best RankIC `hgb_bagged` **0.1380** (≪ abs/h1 0.2546). Selective 0 emits. Best cost −0.29% net@112. Horizon lever exhausted for absolute too.

## Absolute/h3 (2026-07-24) — exhausted

Nested absolute/h3 on split snapshot (`CPU_EXHAUST_ABS_H3_20260724.md`):

| Model | RankIC | Selective | Best net@112 |
|---|---:|---|---:|
| `hgb_bagged` | **0.2061** | 0 emits | −1.21% daily L/S |
| `xgb_two_stage` | 0.2014 | 0 emits | −1.06% |
| `double_ensemble_native` | 0.1790 | 0 emits | **+0.69%** (`weekly_5_sessions_top_bottom_05`) |

Below abs/h1 champion 0.2546 and rel/h3 0.2285. Selective 90% **unmet**.
Champions unchanged.

## W1 feature pack v2 (2026-07-24) — exhausted, no materiality

Nested relative/h1 with `--feature-pack v2` (`FEATURE_PACK_V2_NESTED_20260724.md`,
`cpu_exhaust_rel_h1_fpv2_summary.json`). W5 2k hyper on same matrix in
`CPU_W5_FPV2_2K_20260724.md` — hyper exhausted.

| Model | Frozen RankIC | fpv2 RankIC | Δ | Selective (xgb) | DE persist net@112 |
|---|---:|---:|---:|---|---:|
| `xgb_two_stage` | **0.2861** | 0.2865 | +0.0004 | 105 / LCB 0.688 | — |
| `hgb_two_stage` | 0.2816 | 0.2836 | +0.0020 | 73 / LCB 0.662 | — |
| `double_ensemble_native` | 0.2566 | 0.2553 | −0.0013 | 0 emits | +0.41% (vs +0.49%) |

W1 materiality **not fired**. Selective 90% contract **still unmet** (honest).
**Champions retained:** RankIC `xgb_two_stage` 0.2861; cost DE persist +0.49%.

## Cycle — 2026-07-24 simple models (fpv2)

- Matrix: `feature_pack_v2` / relative / h1 — models `ridge_return`, `logistic`,
  `xgb_regressor`, `hgb_regressor` (+ DE survivor).
- Best nested RankIC: `xgb_regressor` **0.2625** (−0.0236 vs frozen 0.2861).
- Selective: **0 emits** all models; SuccessContract **NOT MET**.
- Evidence: `SIMPLE_MODELS_NESTED_20260724.md`, `cpu_exhaust_rel_h1_simple_summary.json`.
- Next serial (in flight): remaining families `hgb_weighted,hgb_domain,xgb_domain,lgb_lmt,lgb_domain,qlib_lgb_native` then near-miss disagreement trio.

