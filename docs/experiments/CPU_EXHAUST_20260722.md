# CPU exhaust ladder — 2026-07-22/23

Status: **relative/h1 + absolute/h1 nested complete; 10 000 LGB done;
cost-engineering flipped net@112bps positive offline; selective gates
and ensembles exhausted; 6×1000 improve loops still running; split
adjustment path landed (needs re-score).**

## Goal

Beat prior DoubleEnsemble RankIC **0.2526** and clear the selective 90%
precision/LCB contract and/or positive post-cost @112 bps.

## Snapshot

- `bars_sha256`: `dc7de31d5c9ac46f17d878aee89676306da1959ff0b006badc7020a4a00f1da7`
- 917 087 rows / 292 symbols / 2000-01-03 → 2026-07-21

## Relative / h1 — nested (17 529 rows / 117 sessions)

| model | RankIC | BA | MCC | net@112bps |
|---|---:|---:|---:|---:|
| **xgb_two_stage** | **0.2861** | **0.5882** | 0.1771 | −0.78% |
| xgb_lmt | 0.2836 | 0.5857 | 0.1721 | −1.02% |
| hgb_two_stage | 0.2816 | 0.5857 | 0.1787 | −0.88% |
| hgb_lmt | 0.2806 | 0.5840 | 0.1748 | −1.13% |
| hgb_bagged | 0.2748 | 0.5760 | 0.1801 | −1.03% |
| hgb_deep | 0.2748 | 0.5757 | 0.1801 | −1.03% |
| double_ensemble_native | 0.2566 | 0.5777 | 0.1538 | −0.44% |

## Relative / h1 — 10 000 LightGBM screen

Best fold-0 test winner: `lgb_c34120c27d` RankIC **0.2640** (beats
DoubleEnsemble, loses to nested `xgb_two_stage`). Post-cost still
negative. See `cpu_exhaust_rel_h1_lgb_10k.json`.

## Absolute / h1 — nested (19 928 rows / 117 sessions)

| model | RankIC | BA | MCC | net@112bps |
|---|---:|---:|---:|---:|
| **hgb_bagged** | **0.2546** | **0.5883** | 0.1812 | −1.32% |
| xgb_two_stage | 0.2474 | 0.5757 | 0.1510 | −1.32% |
| hgb_deep | 0.2445 | 0.5881 | 0.1819 | −1.43% |
| hgb_two_stage | 0.2433 | 0.5822 | 0.1643 | −1.29% |
| xgb_lmt | 0.2425 | 0.5787 | 0.1568 | −1.36% |
| hgb_weighted | 0.2387 | 0.5730 | 0.1457 | −1.23% |
| double_ensemble_native | 0.2286 | 0.5634 | 0.1283 | −0.86% |

Absolute skill is real but weaker than relative; contract still unmet;
post-cost still negative.

## Improvement loops (operator request)

Base 10 000 already done. Now running `koel/ml/cpu_improve_loop.py`:

1. **+1 000** improvement configs (LGB neighbourhood, select on cal net@112)
2. **×5 more cycles** of 1 000 each (XGB grid, blends, seeded LGB,
   cost-shaped labels, mixed hunt) → **6 000 total** improvement configs

Selection metric prefers calibration **net spread @112 bps**, then RankIC.
Test scored once for top-5 winners per cycle.

## Still not promotion-ready

- selective 90% precision/LCB: **not met**
- post-cost @112 bps: **negative** across every nested survivor so far
- relative `xgb_two_stage` remains the RankIC champion

## Safety

- `live_shadow.py` / policy IDs untouched
- no `forecast_points` / Telegram writes
- hyperparameter / improvement selection is calibration-only
