# Universe filter liq_v1 — nested relative/h1 (2026-07-23)

Research only — not financial advice. No buy/sell language. SuccessContract
**still unmet** — `nested_contract_met: false`; offline selective 90% gates not
reached; no promotion.

## Run identity

| Field | Value |
|---|---|
| Matrix | `liq_v1` / relative / h1 / CSE |
| Snapshot | split-adjusted (`bb49b183b83585a2…`) |
| Filter | `--universe-filter liq_v1` (ADV20 ≥1000, flat60 ≤0.40, CSE sessions ≥20) |
| Models | `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Nested | 3 folds × seeds 0,1,2 (requested) |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-liqv1` |
| Post-process | `/tmp/cpu-post-rel-h1-liqv1` |
| Summary JSON | `cpu_exhaust_rel_h1_liqv1_summary.json` |

Spec: `UNIVERSE_FILTER_LIQ_V1_SPEC.md`. Parent plan: `ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md` §W2.

Sample impact: **502 908 → 32 535** rows (−93.5%) after filter; nested sessions
**117 → 78** for the sole survivor.

---

## Nested RankIC vs frozen h1 champions

Frozen baseline: `cpu_exhaust_rel_h1_summary.json` (no universe filter).

| Model | Frozen RankIC | liq_v1 RankIC | Δ RankIC | Status |
|---|---:|---:|---:|---|
| **`xgb_two_stage`** | **0.2861** | n/a | — | screen fail: insufficient train/test samples |
| `hgb_two_stage` | 0.2816 | n/a | — | screen fail: insufficient train/test samples |
| `double_ensemble_native` | 0.2566 | 0.1813* | **−0.0753** | partial nested (2/3 folds; fold 0 failed) |

\*Pooled over folds 1–2 only; `beats_baseline: false`.

Frozen cost champion (split-adjusted): DE `persistence_exit_10_top_bottom_05`
**+0.49%** net@112 (`ML_SPLIT_COST_COMPARE_20260723.md`).

### Headline

- **W2 kill:** filter collapses eligible universe; xgb/hgb cannot train nested
  splits. Only DE produced partial shards.
- **No RankIC challenger.** Best available liq_v1 RankIC (DE 0.1813) is **0.1048
  below** frozen xgb champion 0.2861 — far outside W2 materiality.
- **No selective progress:** 0 calibration-safe emits (vs frozen xgb 74 emits /
  0.770 prec / LCB 0.681).
- **No cost flip:** best liq_v1 net@112 is **−0.40%** (DE `min_hold_5_top_bottom_10`);
  persistence variant **−1.01%** (vs frozen DE persist **+0.49%**).

---

## W2 exit / kill criteria (master plan)

| Criterion | Fired? | Evidence |
|---|---|---|
| Selective emits ≥2× | **No** | 0 vs frozen xgb 74 |
| Precision LCB ≥0.75 @ ≥100 emits | **No** | 0 emits |
| net@112 +0.10 pp vs unfiltered | **No** | best −0.40% vs frozen +0.49% |
| Filter removes >50% sessions w/o progress | **Yes (kill)** | 117 → 78 sessions; xgb/hgb dead |

**Verdict:** W2 `liq_v1` **killed** on this threshold grid. Lever status:
**exhausted / reject preset** — not promoted. fp+liq combo run continues for
completeness but inherits the same universe collapse risk.

---

## Selective gates (90% contract)

**NOT MET** — `contract_met: false` for all evaluable models.

| Model | Contract | Precision | LCB | Emits | Symbols | Coverage |
|---|:---:|---:|---:|---:|---:|---:|
| `xgb_two_stage` | n/a | n/a | n/a | n/a | n/a | n/a |
| `hgb_two_stage` | n/a | n/a | n/a | n/a | n/a | n/a |
| `double_ensemble_native` | **false** | — | — | **0** | 0 | 0.0 |

vs frozen baseline (`SELECTIVE_GATES_20260723.md`): xgb **74 emits / 0.770 prec /
LCB 0.681** — liq_v1 moves backward, not toward Goal A.

---

## Cost engineering @112 bps (liq_v1 shards — DE only)

| Model | Best variant | Net | Gross | Turnover | Sessions |
|---|---|---:|---:|---:|---:|
| `double_ensemble_native` | `min_hold_5_top_bottom_10` | **−0.40%** | 0.79% | 0.529 | 78 |
| `double_ensemble_native` | `persistence_exit_10_top_bottom_05` | −1.01% | 2.63% | 1.625 | 78 |
| `xgb_two_stage` | n/a | n/a | n/a | n/a | n/a |
| `hgb_two_stage` | n/a | n/a | n/a | n/a | n/a |

Post-process artifacts: `/tmp/cpu-post-rel-h1-liqv1/cost/`,
`/tmp/cpu-post-rel-h1-liqv1/selective/`.

---

## Promotion contract

**Contract: NOT MET.** `nested_contract_met: false`. Frozen RankIC champion
(`xgb_two_stage` 0.2861) and split-adjusted cost champion (DE persist +0.49%)
**retained**. Universe filter `liq_v1` remains research-only; not wired to
`live_shadow`. No `forecast_points`.
