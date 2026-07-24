# Feature pack v2 — nested relative/h1 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet** — offline
selective 90% gates not reached; no promotion.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v2` / relative / h1 / CSE |
| Snapshot | split-adjusted (`fc4d730527d4821f…`) — 2026-07-24 queue export |
| Sector map | `/tmp/koel-sector-map.json` (296 symbols) |
| Models | `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Nested | 3 folds × seeds 0,1,2 |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-fpv2` |
| Post-process | `/tmp/cpu-post-rel-h1-fpv2` |
| Summary JSON | `cpu_exhaust_rel_h1_fpv2_summary.json` |

Spec: `FEATURE_PACK_V2_SPEC.md`. Queue step 2 failed initially on missing ML
deps (`xgboost`, `sklearn`, `lightgbm`); recovery re-run after pip install and
queue completion (`/tmp/koel-recovery-step2.sh`).

---

## Nested RankIC vs frozen h1 champions

Frozen baseline: `cpu_exhaust_rel_h1_summary.json` (same split snapshot, no
feature pack). Champion RankIC **0.2861** (`xgb_two_stage`).

| Model | Frozen RankIC | fpv2 RankIC | Δ RankIC | Frozen net@112 | fpv2 best net@112 |
|---|---:|---:|---:|---:|---:|
| **`xgb_two_stage`** | **0.2861** | 0.2865 | **+0.0004** | −0.78% | −0.70% daily L/S |
| `hgb_two_stage` | 0.2816 | 0.2836 | +0.0020 | −0.88% | −0.87% |
| `double_ensemble_native` | 0.2566 | 0.2553 | −0.0013 | −0.44% | **+0.41%** (`persistence_exit_10_top_bottom_05`) |

Frozen cost champion (split-adjusted): DE `persistence_exit_10_top_bottom_05`
**+0.49%** net@112 (`ML_SPLIT_COST_COMPARE_20260723.md`).

### Headline

- **No RankIC challenger.** fpv2 xgb 0.2865 is **+0.0004** above frozen 0.2861
  — well under W1 materiality (+0.005). Within fold noise (single folds hit
  0.308 test RankIC but nested aggregate does not clear threshold).
- DE persist +0.41% vs frozen +0.49% (**−0.08 pp**) — below W1 net@112 (+0.10 pp).
- Sector-relative features (v2) perform **similar to v1** (which regressed
  −0.0007) — neither clears W1.

---

## W1 materiality thresholds (master plan)

| Threshold | Fired? | Evidence |
|---|---|---|
| RankIC **+0.005** | **No** | Best Δ = +0.0020 (hgb); xgb +0.0004 |
| net@112 **+0.10 pp** | **No** | DE persist −0.08 pp vs frozen +0.49% |
| Selective emits **2×** | **No** | xgb 1.42× (105 vs 74); hgb 0.85× |

**Verdict:** W1 feature pack v2 **does not clear materiality**. Lever status:
**exhausted / no unlock** (same as v1). Frozen RankIC champion retained.

---

## Selective gates (90% contract) — honesty vs frozen

**NOT MET** for any model.

| Model | Contract | Precision | LCB | Emits | vs frozen |
|---|:---:|---:|---:|---:|---|
| `xgb_two_stage` | false | 0.762 | 0.688 | 105 | 74 / 0.770 / 0.681 |
| `hgb_two_stage` | false | 0.753 | 0.662 | 73 | 86 / 0.755 / 0.676 |
| `double_ensemble_native` | false | — | — | 0 | 0 emits |

fpv2 xgb emits **more** (+42%) at slightly lower point precision; LCB 0.688
vs frozen 0.681 — both **far below 0.90 floor**. Contract honesty:
**still false**, no promotion path. Reporting unchanged vs
`SELECTIVE_GATES_20260723.md` baseline.

---

## Cost engineering @112 bps (fpv2 shards)

| Model | Best variant | Net | Gross | Sessions |
|---|---|---:|---:|---:|
| `double_ensemble_native` | `persistence_exit_10_top_bottom_05` | **+0.41%** | — | 117 |
| `xgb_two_stage` | baseline daily L/S | −0.70% | — | 117 |
| `hgb_two_stage` | baseline daily L/S | −0.87% | — | 117 |

No improvement vs frozen split-adjusted cost table. DE persist remains
review-eligible at +0.49% on **frozen** scores, not fpv2.

---

## Comparison summary (fpv2 vs frozen xgb 0.2861)

| Metric | Frozen | fpv2 | Verdict |
|---|---:|---:|---|
| Nested RankIC (xgb) | 0.2861 | 0.2865 | +0.0004 — noise |
| Selective emits (xgb) | 74 | 105 | more coverage, contract still false |
| Selective LCB (xgb) | 0.681 | 0.688 | no 90% unlock |
| DE persist net@112 | +0.49% | +0.41% | regression |

Champions unchanged. SuccessContract **still unmet**.
