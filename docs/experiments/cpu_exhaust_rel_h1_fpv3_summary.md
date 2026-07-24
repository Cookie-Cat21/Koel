# CPU exhaust summary

- run_id: `cpu-exhaust-1784890069`
- snapshot: `fc4d730527d4821f331369640f9113e8e035171ab1a04e085aed3843650e56ae`
- target/horizon/domain: `relative` / h1 / `cse`
- baseline RankIC (DoubleEnsemble): 0.2526
- feature_pack: `v3`
- universe_filter: `none`
- sample_weight: `none`
- any_beats_baseline: **True**
- nested contract_met: `False`

## Family screen (fold 0)

| model | cal RankIC | test RankIC | error |
|---|---:|---:|---|
| hgb_two_stage | 0.2563689771136537 | 0.28390822960881573 |  |
| xgb_two_stage | 0.2548546276978362 | 0.2832700771783484 |  |
| double_ensemble_native | 0.21638654991716982 | 0.2581716466380419 |  |

## Nested pooled (survivors)

| model | RankIC | BA | MCC | spread@112 | beats baseline |
|---|---:|---:|---:|---:|---|
| xgb_two_stage | 0.2843261233486414 | 0.5844905681000254 | 0.1706726038097969 | -0.0070955027900320876 | True |
| hgb_two_stage | 0.2833233956635547 | 0.5815971453170746 | 0.17066945165498768 | -0.008570958544581156 | True |
| double_ensemble_native | 0.25302752186894867 | 0.5775498587550044 | 0.15364541068724188 | -0.004939570974483098 | True |

## 10k LightGBM winners (test once)

