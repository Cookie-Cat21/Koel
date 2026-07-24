# Goal A wave5 abs+matmed — 2026-07-24T21:11:27.170183+00:00

- `cpu-sel-abs-matmed` `hgb_bagged.selective_gates.json` contract=False prec=0.8882 LCB=0.8391 emits=152
- `cpu-metalabel-abs-matmed` `xgb_lmt.selective_metalabel_rich.json` contract=False prec=0.8825 LCB=0.8494 emits=315
- `cpu-disagree-abs-matmed` `xgb_two_stage.selective_disagreement.stdev.json` contract=False prec=0.8014 LCB=0.7407 emits=141
- nest RankIC: {'hgb_bagged': 0.28921501078477396, 'xgb_two_stage': 0.2791812976240481, 'xgb_lmt': 0.27279693944180744, 'double_ensemble_native': 0.2683271757320723}
- nested_contract_met=False

ANY_CONTRACT_MET=False

