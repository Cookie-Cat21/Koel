# Universe filter liq_v2 — nested relative/h1 (2026-07-23)

Research only — not financial advice. No buy/sell language. SuccessContract
**still unmet** — `nested_contract_met: false`; offline selective 90% gates not
reached; no promotion.

## Run identity

| Field | Value |
|---|---|
| Matrix | `liq_v2` / relative / h1 / CSE |
| Snapshot | split-adjusted (`a57bce8bdd9fba7b…`) |
| Filter | `--universe-filter liq_v2` (ADV20 ≥100, flat60 ≤0.50, CSE sessions ≥10) |
| Models | `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Nested | 3 folds × seeds 0,1,2 |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-liqv2` |
| Post-process | `/tmp/cpu-post-rel-h1-liqv2` |
| Summary JSON | `cpu_exhaust_rel_h1_liqv2_summary.json` |

Spec: `UNIVERSE_FILTER_LIQ_V2_SPEC.md`. Parent plan: `ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md` §W2.

Sample impact: **636 455 → 35 328** rows (−94.4%) after filter on the same split
snapshot family as h3; nested test rows **18 212** (117 sessions).

**Kill signal:** post-filter sample count **<100 000** — same order of collapse as
liq_v1 despite relaxed thresholds.

---

## Nested RankIC vs frozen h1 champions

Frozen baseline: `cpu_exhaust_rel_h1_summary.json` (no universe filter).

| Model | Frozen RankIC | liq_v2 RankIC | Δ RankIC | Status |
|---|---:|---:|---:|---|
| **`xgb_two_stage`** | **0.2861** | 0.2136 | **−0.0725** | full nested |
| `hgb_two_stage` | 0.2816 | 0.1981 | −0.0835 | full nested |
| `double_ensemble_native` | 0.2566 | 0.1783 | −0.0783 | full nested |

Frozen cost champion (split-adjusted): DE `persistence_exit_10_top_bottom_05`
**+0.49%** net@112 (`ML_SPLIT_COST_COMPARE_20260723.md`).

### Headline

- **W2 kill (softened but still collapsed):** liq_v2 retains only **5.6%** of
  training rows; well below the 100 k sample floor used for W2 continuation.
- **No RankIC challenger.** Best liq_v2 RankIC (xgb 0.2136) is **0.0725 below**
  frozen xgb champion — far outside W2 materiality.
- **No selective progress:** 0 calibration-safe emits for all three models (vs
  frozen xgb 74 emits / 0.770 prec / LCB 0.681).
- **No cost flip:** best liq_v2 net@112 is **−0.34%** (DE `weekly_5_sessions_top_bottom_05`);
  persistence variants also negative.

Unlike liq_v1, all three models completed nested splits — the relaxed manifest
fixed screen failures but **did not** restore sample depth or score quality.

---

## W2 exit / kill criteria (master plan)

| Criterion | Fired? | Evidence |
|---|---|---|
| Sample count ≥100 k post-filter | **No** | 35 328 rows |
| Selective emits ≥2× | **No** | 0 vs frozen xgb 74 |
| Precision LCB ≥0.75 @ ≥100 emits | **No** | 0 emits |
| RankIC within 0.005 of frozen | **No** | Δ −0.0725 |
| net@112 improvement ≥0.10 pp | **No** | best −0.34% |

**Verdict:** liq_v2 **killed**; preset rejected. See `UNIVERSE_FILTER_LIQ_V3_SPEC.md`
for the next soften step (drop ADV floor; flat-only gate).

---

## Recommendation — liq_v3

If ADV20 and CSE-session gates continue to dominate sample loss:

1. **Drop ADV floor** (`min_adv20=0`) — no volume gate.
2. **Keep flat-fraction gate only** at **0.40** (stricter than v2’s 0.50).
3. **Relax CSE sessions to 5** (from 10).

Manifest declared in `UNIVERSE_FILTER_LIQ_V3_SPEC.md`; nested relative/h1 trio
**started** after this cycle (`/tmp/cpu-exhaust-rel-h1-liqv3`).

Champions unchanged; SuccessContract **still unmet**.
