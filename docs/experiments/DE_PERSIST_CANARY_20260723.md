# DE persist live shadow canary report

## Status

- `koel.ml.live_shadow` exited naturally.
- Traceback: none.
- Partial gate used: yes (`partial_session: true`; gate `shadow_partial_persist_book`).

## Final canary JSON

```json
{"board_rows": 252, "eligible_symbols": 159, "instance_versions": {"shadow_policy_abs_hgb2_v1": "shadow_policy_abs_hgb2_v1__2026-07-23__09275120273cd6b5_partial", "shadow_policy_abs_xgb2_p005_v1": "shadow_policy_abs_xgb2_p005_v1__2026-07-23__3b4b02aeace7e004_partial", "shadow_policy_abs_xgb2_pressure_v1": "shadow_policy_abs_xgb2_pressure_v1__2026-07-23__aef9c06363790a73_partial", "shadow_policy_abs_xgb2_v1": "shadow_policy_abs_xgb2_v1__2026-07-23__7700007d8145e89f_partial", "shadow_policy_abs_xgb_domain_v1": "shadow_policy_abs_xgb_domain_v1__2026-07-23__634f20e1fd77d0d3_partial", "shadow_policy_rank_de_persist_v1": "shadow_policy_rank_de_persist_v1__2026-07-23__d1aae76ca409243b_partial"}, "issued_at": "2026-07-23", "partial_session": true, "policy_emits": {"shadow_policy_abs_hgb2_v1": 159, "shadow_policy_abs_xgb2_v1": 159, "shadow_policy_abs_xgb_domain_v1": 159, "shadow_policy_rank_de_persist_v1": 14}, "pressure_emits": 0, "selective_emits": 1, "snapshot_sha256": "a026fd80558df50a6482b32d3755cbd294b93f79222e5143dd6ecfc03fc6c232"}
```

## Emit counts

- `shadow_policy_abs_hgb2_v1`: 159
- `shadow_policy_abs_xgb2_v1`: 159
- `shadow_policy_abs_xgb_domain_v1`: 159
- `shadow_policy_rank_de_persist_v1`: 14
- selective emits: 1
- pressure emits: 0

## Neon persistence check

- policy id: `shadow_policy_rank_de_persist_v1`
- total `forecast_outcomes` rows for policy id: 14
- current instance rows: 14
- current `issued_at=2026-07-23` rows: 14
- current partial rows: 14
- gates: `shadow_partial_persist_book`
- sample symbols: `AINS.N0000`, `ASIY.N0000`, `CARS.N0000`, `CLND.N0000`, `COLO.N0000`, `EXT.N0000`, `GHLL.N0000`, `HPL.N0000`, `HSIG.N0000`, `KGAL.N0000`

## h5 nested progress tail

```text
[exhaust] loading snapshot from /tmp/koel-live-final-snapshot-split
[exhaust] samples=676554 dates=6678 sha=fc4d730527d4821f… target=relative h=5
[screen] xgb_two_stage: cal_RankIC=0.1478676779922911 test_RankIC=0.16980288475769728 (23.4s)
[screen] double_ensemble_native: cal_RankIC=0.1184986795804113 test_RankIC=0.1659337438376294 (71.8s)
[screen] hgb_two_stage: cal_RankIC=0.15029936003004712 test_RankIC=0.1680635029600351 (23.7s)
[exhaust] deep survivors: ['hgb_two_stage', 'xgb_two_stage', 'double_ensemble_native']
[nested] hgb_two_stage fold=0: test_RankIC=0.17327374747810592 (1305.6s)
[nested] hgb_two_stage fold=1: test_RankIC=0.11280692446943989 (1813.1s)
[nested] hgb_two_stage fold=2: test_RankIC=0.23251264310320754 (1151.3s)
```
