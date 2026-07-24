# CPU exhaust summary

- run_id: `cpu-exhaust-1784886747`
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
| lgb_lmt | 0.24754256321125795 | 0.2827461380129498 |  |
| lgb_domain | 0.23296230494704534 | 0.25825325352738016 |  |
| hgb_weighted | 0.22796931194391687 | 0.26402123706418096 |  |
| xgb_domain | 0.22464491784851331 | 0.2590045982101679 |  |
| hgb_domain | 0.2178300889351441 | 0.24713077910909745 |  |
| qlib_lgb_native | 0.1710725964430285 | 0.21750825069734986 |  |

## Nested pooled (survivors)

| model | RankIC | BA | MCC | spread@112 | beats baseline |
|---|---:|---:|---:|---:|---|
| lgb_lmt | 0.28141390815712164 | 0.586889287671994 | 0.17415387633099996 | -0.01092891557549234 | True |
| hgb_weighted | 0.2629312483481494 | 0.5826114120020518 | 0.1673798836253281 | -0.006579898206404266 | True |
| lgb_domain | 0.2555319422048956 | 0.572572986934348 | 0.14463400136323584 | -0.014476814709455343 | True |
| double_ensemble_native | 0.25527003784782265 | 0.5786931535328677 | 0.1557269469610821 | -0.004179919238137414 | True |

## 10k LightGBM winners (test once)

