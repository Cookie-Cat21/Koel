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

E7 requires ≥60 **non-partial scored** sessions — scheduled final emit after 14:35 SLT.

## Levers exhausted offline

Same-matrix hypers, ensembles, selective grids, fpv1/v2, liq filters v1–v3, horizons h3/h5, CSE-only short history, ADV sample weights, disagreement selective.

## Still open

- E7 non-partial shadow receipts
- E8 prospective vs offline
- E10 finalize this dossier
- Optional: further feature hypotheses if any material signal appears

