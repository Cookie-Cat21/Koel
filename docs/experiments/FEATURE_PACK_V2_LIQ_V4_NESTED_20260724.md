# Feature pack v2 + liq_v4 combo — nested relative/h1 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet**.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v2` + `liq_v4` / relative / h1 |
| Snapshot | `2f7031a8f61a03a3…` |
| Models | baseline trio |
| Exhaust | `/tmp/cpu-exhaust-rel-h1-fpv2-liqv4` |

## Nested RankIC vs frozen 0.2861

| Model | RankIC | Δ |
|---|---:|---:|
| `xgb_two_stage` | **0.2835** | -0.0026 |
| `hgb_two_stage` | **0.2823** | -0.0038 |
| `double_ensemble_native` | **0.2532** | -0.0329 |

## Selective

| Model | Contract | Precision | LCB | Emits |
|---|:---:|---:|---:|---:|
| `double_ensemble_native` | False | None | None | 0 |
| `hgb_two_stage` | False | 0.7830188679245284 | 0.7105667697883257 | 106 |
| `xgb_two_stage` | False | 0.7972972972972973 | 0.7105851664048203 | 74 |

## Cost @112

- best: `double_ensemble_native` / `persistence_exit_10_top_bottom_05` net=`0.006001380813429479`

## Materiality

| Gate | Result | Fired? |
|---|---|:---:|
| RankIC +0.005 | Δ **-0.0026** | False |
| net@112 +0.10pp | `0.006001380813429479` | True |
| Selective 2× | emits **106** | False |

**Verdict: MATERIALITY MET on net@112 — unblock W5.**

Cost gate fired: DE `persistence_exit_10_top_bottom_05` net **+0.60%** vs frozen
champion **+0.49%** (**+0.11 pp** ≥ +0.10 pp). RankIC and selective emits did
**not** fire. SuccessContract still **NOT MET**. Proceed to capped W5 search on
this `matrix_id` only.

Research only — not financial advice.
