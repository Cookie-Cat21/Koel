# Feature pack v1 — nested relative/h1 (2026-07-23)

Research only — not financial advice. No buy/sell language. SuccessContract
**still unmet** — offline selective 90% gates not reached; no promotion.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v1` / relative / h1 / CSE |
| Snapshot | split-adjusted (`fc4d730527d4821f…`) |
| Models | `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Nested | 3 folds × seeds 0,1,2 |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-fpv1` |
| Post-process | `/tmp/cpu-post-rel-h1-fpv1` |
| Summary JSON | `cpu_exhaust_rel_h1_fpv1_summary.json` |

Spec: `FEATURE_PACK_V1_SPEC.md`. Parent plan: `ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md` §W1.

---

## Nested RankIC vs frozen h1 champions

Frozen baseline artifacts: `cpu_exhaust_rel_h1_summary.json` (same split snapshot,
**no** feature pack).

| Model | Frozen RankIC | fpv1 RankIC | Δ RankIC | Frozen net@112 (daily L/S) | fpv1 best net@112 |
|---|---:|---:|---:|---:|---:|
| **`xgb_two_stage`** | **0.2861** | 0.2854 | **−0.0007** | −0.78% | −0.06% (`min_hold_3_top_bottom_10`) |
| `hgb_two_stage` | 0.2816 | 0.2809 | −0.0007 | −0.88% | −0.07% (`min_hold_5_top_bottom_10`) |
| `double_ensemble_native` | 0.2566 | 0.2510 | −0.0056 | −0.44% | **+0.53%** (`persistence_exit_10_top_bottom_05`) |

Frozen cost champion (split-adjusted): DE `persistence_exit_10_top_bottom_05`
**+0.49%** net@112 (`ML_SPLIT_COST_COMPARE_20260723.md`).

### Headline

- **No RankIC challenger.** Best fpv1 RankIC (`xgb_two_stage` 0.2854) is **0.0007
  below** frozen champion 0.2861 — well under W1 materiality (+0.005).
- **DE cost variant marginally higher** (+0.53% vs +0.49%, Δ **+0.04 pp**) — below
  W1 net@112 materiality (+0.10 pp). Not a new champion; within noise.
- `double_ensemble_native` RankIC **regressed** (−0.0056) and no longer beats
  Qlib baseline offline on this matrix.
- Daily top/bottom L/S (`spread_112`) remains negative for all three without
  persistence construction.

---

## W1 materiality thresholds (master plan)

| Threshold | Fired? | Evidence |
|---|---|---|
| RankIC **+0.005** | **No** | Best Δ = −0.0007 (`xgb_two_stage`) |
| net@112 **+0.10 pp** | **No** | Best Δ = +0.04 pp (DE persist vs frozen +0.49%) |
| Selective emits **2×** at same coverage grid | **No** | xgb 94 vs 74 (1.27×); hgb 94 vs 86 (1.09×) |

**Verdict:** W1 feature pack v1 **does not clear materiality** on this nested
pass. Lever status remains **started / inconclusive** — not promoted.

---

## Selective gates (90% contract)

**NOT MET** for any model (same contract as frozen h1).

| Model | Contract | Precision | LCB | Emits | Symbols | Coverage |
|---|:---:|---:|---:|---:|---:|---:|
| `xgb_two_stage` | false | 0.745 | 0.665 | 94 | 47 | 0.0052 |
| `hgb_two_stage` | false | 0.755 | 0.676 | 94 | 49 | 0.0052 |
| `double_ensemble_native` | false | — | — | 0 | 0 | 0.0 |

vs frozen baseline (`SELECTIVE_GATES_20260723.md`): xgb 74 emits, hgb 86 emits.
Slightly more emits at similar coverage but far below 500-emit / 0.90 LCB floors.

---

## Cost engineering @112 bps (fpv1 shards)

| Model | Best variant | Net | Gross | Turnover | Sessions |
|---|---|---:|---:|---:|---:|
| `double_ensemble_native` | `persistence_exit_10_top_bottom_05` | **+0.53%** | 3.64% | 1.387 | 117 |
| `hgb_two_stage` | `min_hold_5_top_bottom_10` | −0.07% | 1.16% | 0.550 | 117 |
| `xgb_two_stage` | `min_hold_3_top_bottom_10` | −0.06% | 1.63% | 0.754 | 117 |

Post-process artifacts: `/tmp/cpu-post-rel-h1-fpv1/cost/`,
`/tmp/cpu-post-rel-h1-fpv1/selective/`.

---

## Promotion contract

**Contract: NOT MET.** Nested selective 90% false; global hard gates unchanged.
Frozen RankIC champion (`xgb_two_stage` 0.2861) and split-adjusted cost champion
(DE persist +0.49%) **retained**. Feature pack v1 remains research-only behind
`--feature-pack v1`; not wired to `live_shadow`.
