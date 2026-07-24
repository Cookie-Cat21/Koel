# CPU exhaust summary

- run_id: `cpu-exhaust-1784885135`
- snapshot: `fc4d730527d4821f331369640f9113e8e035171ab1a04e085aed3843650e56ae`
- target/horizon/domain: `relative` / h1 / `cse`
- baseline RankIC (DoubleEnsemble): 0.2526
- feature_pack: `v2`
- universe_filter: `none`
- sample_weight: `none`
- any_beats_baseline: **True**
- nested contract_met: `False`

## Family screen (fold 0)

| model | cal RankIC | test RankIC | error |
|---|---:|---:|---|
| xgb_regressor | 0.2330552890730961 | 0.2629768991374018 |  |
| hgb_regressor | 0.21901319350094245 | 0.25556530158435836 |  |
| logistic | 0.16417730913420386 | 0.20902469652527267 |  |
| ridge_return | 0.14892351998596698 | 0.20296065205094374 |  |

## Nested pooled (survivors)

| model | RankIC | BA | MCC | spread@112 | beats baseline |
|---|---:|---:|---:|---:|---|
| xgb_regressor | 0.2624530722041269 | 0.5837494993128238 | 0.16993987344888722 | -0.005920191262933183 | True |
| hgb_regressor | 0.25951591549722064 | 0.5834823716577521 | 0.16817578817771153 | -0.006263718416512157 | True |
| double_ensemble_native | 0.25527003784782265 | 0.5786931535328677 | 0.1557269469610821 | -0.004179919238137414 | True |
| logistic | 0.2220884055722563 | 0.5064699235065606 | 0.013525560392586098 | -0.015026078615373126 | False |

## 10k LightGBM winners (test once)

