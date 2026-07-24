# Feature pack v3 nested — relative/h1 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet**.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v3` / relative / h1 / CSE |
| Snapshot | split-adjusted (`fc4d730527d4821f…`) |
| Models | baseline trio `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Spec | `FEATURE_PACK_V3_SPEC.md` |
| Exhaust | `/tmp/cpu-exhaust-rel-h1-fpv3` |
| Summary | `cpu_exhaust_rel_h1_fpv3_summary.json` |

## Nested RankIC vs frozen champion 0.2861

| Model | Nested RankIC | Δ |
|---|---:|---:|
| `xgb_two_stage` | **0.2843** | -0.0018 |
| `hgb_two_stage` | **0.2833** | -0.0028 |
| `double_ensemble_native` | **0.2530** | -0.0331 |

## Selective gates

| Model | Contract | Precision | LCB | Emits |
|---|:---:|---:|---:|---:|
| `double_ensemble_native` | False | None | None | 0 |
| `hgb_two_stage` | False | 0.78125 | 0.6858088206253751 | 64 |
| `xgb_two_stage` | False | 0.7608695652173914 | 0.6809367473917836 | 92 |

## Cost @112

- best: `double_ensemble_native` / `persistence_exit_10_top_bottom_05` net=`0.005068132247143181`

## W1 materiality

| Gate | Threshold | Result | Fired? |
|---|---|---|:---:|
| RankIC | +0.005 | best Δ **-0.0018** (`xgb_two_stage`) | False |
| net@112 | +0.10 pp vs +0.49% | best net `0.005068132247143181` | False |
| Selective emits | 2× vs 74 | best emits **92** | False |

**Verdict: Killed — no materiality.** No W5 unlock. Champions retained. SuccessContract **NOT MET**.

## Post-nested dense selective + disagreement

| Variant | Precision | LCB | Emits | Contract |
|---|---:|---:|---:|:---:|
| dense `xgb_two_stage` | 0.760 | 0.671 | 75 | false |
| dense `hgb_two_stage` | 0.781 | 0.686 | 64 | false |
| disagreement primary xgb | 0.750 | 0.658 | 72 | false |

No unlock vs default selective. Lever remains **killed**.

Research only — not financial advice.
