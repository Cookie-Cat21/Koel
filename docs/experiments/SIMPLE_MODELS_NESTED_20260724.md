# Simple models nested — fpv2 relative/h1 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet** — no
promotion.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v2` / relative / h1 / CSE |
| Snapshot | split-adjusted (`fc4d730527d4821f…`) |
| Models | `ridge_return`, `logistic`, `xgb_regressor`, `hgb_regressor` (+ DE survivor) |
| Nested | 3 folds × seeds 0,1,2 |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-simple` |
| Post-process | `/tmp/cpu-post-rel-h1-simple` |
| Summary JSON | `cpu_exhaust_rel_h1_simple_summary.json` |

---

## Nested RankIC vs frozen champion

Frozen baseline: `cpu_exhaust_rel_h1_summary.json` — `xgb_two_stage` RankIC
**0.2861**.

| Model | Nested RankIC | Δ vs frozen | Beats screen baseline 0.2526 |
|---|---:|---:|:---:|
| `xgb_regressor` | **0.2625** | -0.0236 | True |
| `hgb_regressor` | **0.2595** | -0.0266 | True |
| `double_ensemble_native` | **0.2553** | -0.0308 | True |
| `logistic` | **0.2221** | -0.0640 | False |

**Verdict:** Best simple challenger `xgb_regressor` at **0.2625** is
**-0.0236** vs frozen `xgb_two_stage` 0.2861 — under W1
+0.005 materiality. Lever **exhausted** (no Goal A unlock).

---

## Selective gates (90% contract)

**NOT MET** for any model (0 emits under default selective grid).

| Model | Contract | Precision | LCB | Emits |
|---|:---:|---:|---:|---:|
| `double_ensemble_native` | False | None | None | 0 |
| `hgb_regressor` | False | None | None | 0 |
| `logistic` | False | None | None | 0 |
| `xgb_regressor` | False | None | None | 0 |

---

## Cost engineering @112 bps

Best net variant on this matrix:

- **`xgb_regressor` / `persistence_exit_10_top_bottom_05`**: net **+0.51%**
  (gross +3.74%, mean one-way turnover 1.44, 117 sessions)

Comparable to frozen split DE persist **+0.49%** but **does not** beat RankIC
champion and still has **0 selective emits** — no Goal A unlock; no live_shadow
rewire (Loop 0 stays on DE-persist policy IDs).

Research only — not financial advice.
