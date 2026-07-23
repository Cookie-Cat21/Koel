# Ensemble stack loop 1 - survivor blends

Offline evaluation only. No retraining and no live policies were registered.

- Input shards: `/tmp/cpu-exhaust-rel-h1/nested`
- Partitions: calibration for weight selection, test for one final score
- Survivor count: 7
- Reference: `xgb_two_stage` RankIC 0.2861
- Cost check: `persistence_exit_10_top_bottom_05` at 112 bps

## Headline

- Best test RankIC blend: `rank_average` at 0.2858 (-0.0003 vs `xgb_two_stage` 0.2861).
- Best blend persistence net@112bps: -0.05% (gross 3.54%, turnover 1.604).
- Decision: no blend beats the RankIC reference, and no blend improves persistence net@112bps versus `xgb_two_stage` (0.01%) or the best survivor `double_ensemble_native` (0.36%).

## Test metrics

| Candidate | RankIC | Delta vs 0.2861 | BA | MCC | Persist gross | Persist net@112bps | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|
| `equal_raw` | 0.2854 | -0.0007 | 0.5878 | 0.1865 | 3.62% | -0.04% | 1.635 |
| `rank_average` | 0.2858 | -0.0003 | 0.5917 | 0.1814 | 3.54% | -0.05% | 1.604 |
| `cal_selected_rank_weight` | 0.2852 | -0.0009 | 0.5897 | 0.1775 | 3.40% | -0.23% | 1.622 |

## Calibration-selected weights

Weights are selected independently per outer fold/horizon from the fixed grid using calibration RankIC only; the matching test fold is scored once after selection.

| Fold | Selected grid row | Calibration RankIC | Test rows |
|---:|---|---:|---:|
| 0 | `pair50_hgb_two_stage__hgb_deep` | 0.2622 | 5876 |
| 1 | `pair50_xgb_two_stage__xgb_lmt` | 0.2843 | 5751 |
| 2 | `pair75_hgb_two_stage__25_hgb_bagged` | 0.2778 | 5902 |

## Baseline sanity check

| Model | Test RankIC | BA | MCC | Persist net@112bps |
|---|---:|---:|---:|---:|
| `xgb_two_stage` | 0.2861 | 0.5882 | 0.1771 | 0.01% |
| `xgb_lmt` | 0.2836 | 0.5857 | 0.1721 | -0.35% |
| `hgb_two_stage` | 0.2816 | 0.5857 | 0.1787 | 0.03% |
| `hgb_lmt` | 0.2806 | 0.5840 | 0.1748 | -0.49% |
| `hgb_bagged` | 0.2748 | 0.5760 | 0.1801 | -0.23% |
| `hgb_deep` | 0.2748 | 0.5757 | 0.1801 | -0.18% |
| `double_ensemble_native` | 0.2566 | 0.5777 | 0.1538 | 0.36% |
