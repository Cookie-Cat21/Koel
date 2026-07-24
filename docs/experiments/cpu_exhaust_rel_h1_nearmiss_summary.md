# CPU exhaust summary

- run_id: `cpu-exhaust-1784888328`
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
| xgb_two_stage | 0.25675553288598063 | 0.28089410404189435 |  |
| hgb_lmt | 0.2557407390214916 | 0.27679989225588447 |  |
| xgb_lmt | 0.2507550098127727 | 0.27986646103925245 |  |

## Nested pooled (survivors)

| model | RankIC | BA | MCC | spread@112 | beats baseline |
|---|---:|---:|---:|---:|---|
| xgb_two_stage | 0.28653413291831203 | 0.5856151837858727 | 0.1724723522733287 | -0.0070263874402104395 | True |
| xgb_lmt | 0.28346614042878915 | 0.5858573279242726 | 0.17272979225525414 | -0.010512580945389795 | True |
| hgb_lmt | 0.2816169567482822 | 0.5852304043506372 | 0.1772576228519141 | -0.01122943184991614 | True |
| double_ensemble_native | 0.25527003784782265 | 0.5786931535328677 | 0.1557269469610821 | -0.004179919238137414 | True |

## 10k LightGBM winners (test once)

