# Remaining fpv2 families nested — relative/h1 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet** — no
promotion.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v2` / relative / h1 / CSE |
| Snapshot | split-adjusted (`fc4d730527d4821f…`) |
| Models | `hgb_weighted`, `hgb_domain`, `xgb_domain`, `lgb_lmt`, `lgb_domain`, `qlib_lgb_native` (+ DE survivor) |
| Nested | 3 folds × seeds 0,1,2 |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-remain` |
| Post-process | `/tmp/cpu-post-rel-h1-remain` |
| Summary JSON | `cpu_exhaust_rel_h1_remain_summary.json` |

---

## Nested RankIC vs frozen champion

Frozen baseline: `xgb_two_stage` RankIC **0.2861**.

| Model | Nested RankIC | Δ vs frozen | Beats 0.2526 |
|---|---:|---:|:---:|
| `lgb_lmt` | **0.2814** | -0.0047 | True |
| `hgb_weighted` | **0.2629** | -0.0232 | True |
| `lgb_domain` | **0.2555** | -0.0306 | True |
| `double_ensemble_native` | **0.2553** | -0.0308 | True |

**Verdict:** Best remaining challenger `lgb_lmt` at **0.2814** is
**-0.0047** vs frozen champion — under W1 +0.005
materiality. Lever **exhausted**.

---

## Selective gates (90% contract)

**NOT MET**. Best selective among remain: `hgb_weighted` ~0.738 / 0.636 / 61 emits.

| Model | Contract | Precision | LCB | Emits |
|---|:---:|---:|---:|---:|
| `double_ensemble_native` | False | None | None | 0 |
| `hgb_weighted` | False | 0.7377049180327869 | 0.6363978088184362 | 61 |
| `lgb_domain` | False | None | None | 0 |
| `lgb_lmt` | False | None | None | 0 |

---

## Cost engineering @112 bps

- best: `double_ensemble_native` / `persistence_exit_10_top_bottom_05` net **+0.41%**

No live_shadow rewire. Research only — not financial advice.
