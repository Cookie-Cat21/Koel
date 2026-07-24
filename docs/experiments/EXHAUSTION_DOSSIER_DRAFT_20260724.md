# Exhaustion dossier draft — 2026-07-24

Research only — not financial advice. Living draft until E7–E8 close.

## Goals

- **A:** Selective 90% SuccessContract (precision & LCB ≥0.90, ≥500 emits, …)
- **B:** Exhaustion checklist E1–E10 in `ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md`

## Offline Goal A status: NOT MET

Best near-misses (relative/h1 unless noted):

| Attempt | Best prec / LCB / emits | Notes |
|---|---|---|
| Frozen selective | 0.770 / 0.681 / 74 | baseline |
| fpv2 denser | 0.762 / 0.688 / 105 | more emits, still ≪0.90 |
| Disagreement xgb+hgb | 0.779 / 0.693 / 77 | best LCB so far |
| fpv2 extra xgb_lmt | 0.891 / 0.793 / 46 | high point prec; emits ≪500 |
| fpv2 extra hgb_lmt | 0.852 / 0.776 / 81 | still ≪0.90 LCB floor |
| Ranking lgb_lambdarank | 0 emits | RankIC 0.2647 (−0.021 vs champion) |
| DE blends blend_de_lgb | 0 emits | RankIC 0.2557; net +0.58% cost only |
| adv20 weights | xgb 0 emits selective | RankIC flat |
| fpv2+adv20 | 0.76-ish / 0.685 / 104 | no unlock |
| Absolute denser | 0 emits | |
| Horizons h3/h5 | unmet | h3 hgb 0.681/0.597/91 |

RankIC champion unchanged: `xgb_two_stage` ~0.2861–0.2867 (noise).

## Cost / shadow (Goal B partial)

| Policy | Offline net@112 | Live |
|---|---:|---|
| `shadow_policy_rank_de_persist_v1` | +0.49% (split) | wired; partial canaries only |
| `shadow_policy_rank_de_h3_weekly_v1` | +0.27–0.69% | wired; partial canaries only |

E7 requires ≥60 **non-partial scored** sessions — **1/60** after post-close run
2026-07-24 (16 legs/policy).

## Levers exhausted offline

Same-matrix hypers, ensembles, selective grids, fpv1/v2, fpv2 extra (bagged/LMT/deep), ranking models (LTR), DE blends, liq filters v1–v3, horizons h3/h5, CSE-only short history, ADV sample weights, disagreement selective.

## 2026-07-24 addendum — simple models

- fpv2 simple nest exhausted: best `xgb_regressor` RankIC **0.2625** (no materiality).
- Selective 0 emits; contract false.
- Path-backfill forced (period=2) brought `daily_bars` through **2026-07-24** (~77+ symbols mid-run).
- DE-persist **non-partial scored sessions still 0** (Jul-24 h1 needs Jul-25 close); partial Jul-23 scored 6/22 legs.
- Monday 2026-07-27 14:40 SLT non-partial shadow scheduled (`koel-shadow-mon` tmux).

## Still open

- E7 non-partial shadow receipts (**1/60** sessions; daily accumulation)
- E8 prospective vs offline (scored_legs 0)
- E10 finalize this dossier
- Optional: further feature hypotheses if any material signal appears

