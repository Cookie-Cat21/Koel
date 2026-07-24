# CPU exhaust summary

- run_id: `cpu-exhaust-1784897947`
- snapshot: `2f7031a8f61a03a3fc9cbb0019af050e0a68128832f37ab26d7ac65b3de02fea`
- target/horizon/domain: `relative` / h1 / `cse`
- baseline RankIC (DoubleEnsemble): 0.2526
- feature_pack: `v2`
- universe_filter: `liq_v4`
- sample_weight: `none`
- any_beats_baseline: **True**
- nested contract_met: `False`

## Family screen (fold 0)

| model | cal RankIC | test RankIC | error |
|---|---:|---:|---|
| xgb_two_stage | 0.2558376061791948 | 0.2859718530158543 |  |
| hgb_two_stage | 0.2541570880516407 | 0.28579672254742877 |  |
| double_ensemble_native | 0.2181931143332128 | 0.25479327084207093 |  |

## Nested pooled (survivors)

| model | RankIC | BA | MCC | spread@112 | beats baseline |
|---|---:|---:|---:|---:|---|
| xgb_two_stage | 0.28345986975219606 | 0.5848695080031606 | 0.1704628774440586 | -0.007842180831655634 | True |
| hgb_two_stage | 0.2822894053131555 | 0.5822138453309751 | 0.17065034880814126 | -0.009393184812237401 | True |
| double_ensemble_native | 0.25321727310963454 | 0.5770344412759412 | 0.1527768352972747 | -0.005086661034765613 | True |

## 10k LightGBM winners (test once)

