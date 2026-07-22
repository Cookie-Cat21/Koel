# CPU exhaust ladder — 2026-07-22

Status: **nested deep complete; 10 000 LightGBM screen running**.
GPU ladder retired as the active search.

## Goal

Beat the prior champion — native DoubleEnsemble RankIC **0.2526**
(BA 0.5763, MCC 0.1509, net spread @112 bps −0.69%) — under the same
nested protocol (3 folds, relative target, CSE eval domain, max flat
fraction 0.40). The strict selective 90% precision/LCB contract remains
the promotion bar.

## Snapshot

- `bars_sha256`: `dc7de31d5c9ac46f17d878aee89676306da1959ff0b006badc7020a4a00f1da7`
- `fundamentals_sha256`: `ce153d84cac292ad124478c18dc83467ddaeee2e9842dc12c276386ac06621a2`
- composite used by exhaust: `fc4d730527d4821f…`
- 917 087 rows / 292 symbols / 2000-01-03 → 2026-07-21
- pooled nested test footprint this run: **17 529 rows / 117 sessions**

## Phase 1 — family screen (fold 0, seed 0)

All 22 CPU families completed. Survivors (top-6 by calibration RankIC +
forced DoubleEnsemble champion):

`hgb_two_stage`, `hgb_lmt`, `xgb_lmt`, `hgb_bagged`, `hgb_deep`,
`xgb_two_stage`, `double_ensemble_native`

## Phase 2 — nested deep (3 folds × seeds 0,1,2)

| model | RankIC | BA | MCC | net@112bps | net@30bps | beats prior baseline |
|---|---:|---:|---:|---:|---:|---|
| **xgb_two_stage** | **0.2861** | **0.5882** | 0.1771 | −0.78% | +1.92% | **yes** |
| xgb_lmt | 0.2836 | 0.5857 | 0.1721 | −1.02% | +1.77% | yes |
| hgb_two_stage | 0.2816 | 0.5857 | 0.1787 | −0.88% | +1.85% | yes |
| hgb_lmt | 0.2806 | 0.5840 | 0.1748 | −1.13% | +1.65% | yes |
| hgb_bagged | 0.2748 | 0.5760 | 0.1801 | −1.03% | +1.78% | yes |
| hgb_deep | 0.2748 | 0.5757 | 0.1801 | −1.03% | +1.79% | yes |
| double_ensemble_native | 0.2566 | 0.5777 | 0.1538 | −0.44% | +2.23% | yes (replicated) |

**New CPU champion on RankIC: `xgb_two_stage` at 0.2861** — clear lift
over the prior DoubleEnsemble mark (0.2526 published / 0.2566
replicated here). Balanced accuracy and MCC also improve.

**Still not promotion-ready:**
- selective 90% precision / LCB contract: **not met** (no calibration
  gate cleared the emit/LCB floors on the equal-blend ensemble)
- post-cost spread @112 bps remains **negative** for every survivor
  (best is DoubleEnsemble at −0.44%; `xgb_two_stage` −0.78%)
- @30 bps every survivor is net-positive — the gap is transaction-cost
  / turnover, plus the still-unadjusted corporate-action factor

## Phase 3 — 10 000 LightGBM configs

**Running** on the cloud VM (`--resume`, calibration-only RankIC screen,
top-10 re-scored once on test). Results land in
`/tmp/cpu-exhaust-rel-h1/hyper/lgb_10k_screen.json` and will be copied
into this document when finished.

## Safety

- `live_shadow.py` / policy IDs untouched
- no `forecast_points` / Telegram writes
- hyperparameter selection is calibration-only

## Next (automatic)

1. Finish the 10k LightGBM screen and record winners
2. Run the same ladder for `absolute` h1 and `relative` h5
3. Only register a new live shadow policy ID if a model clears RankIC
   **and** a computable better post-cost picture (or a real selective
   90% gate) — neither is true yet
