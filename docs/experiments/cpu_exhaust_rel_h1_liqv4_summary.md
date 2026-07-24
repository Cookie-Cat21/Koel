# CPU exhaust summary

- run_id: `cpu-exhaust-1784896462`
- snapshot: `2f7031a8f61a03a3fc9cbb0019af050e0a68128832f37ab26d7ac65b3de02fea`
- target/horizon/domain: `relative` / h1 / `cse`
- baseline RankIC (DoubleEnsemble): 0.2526
- feature_pack: `none`
- universe_filter: `liq_v4`
- sample_weight: `none`
- any_beats_baseline: **True**
- nested contract_met: `False`

## Family screen (fold 0)

| model | cal RankIC | test RankIC | error |
|---|---:|---:|---|
| xgb_two_stage | 0.2566422149445026 | 0.2869325865100505 |  |
| hgb_two_stage | 0.2534481566725702 | 0.28146846792114627 |  |
| double_ensemble_native | 0.21086434000922485 | 0.25475449236787706 |  |

## Nested pooled (survivors)

| model | RankIC | BA | MCC | spread@112 | beats baseline |
|---|---:|---:|---:|---:|---|
| xgb_two_stage | 0.2841670597166377 | 0.5866635255295012 | 0.1736184948766885 | -0.007838932240068005 | True |
| hgb_two_stage | 0.2821697527251256 | 0.5850255422640155 | 0.17616521951252556 | -0.01027903590868684 | True |
| double_ensemble_native | 0.2518304707128295 | 0.5763924948584611 | 0.15142979873243634 | -0.005563545203826554 | False |

## 10k LightGBM winners (test once)

