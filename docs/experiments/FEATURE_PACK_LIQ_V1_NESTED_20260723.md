# Feature pack v1 + liq_v1 — nested relative/h1 (2026-07-23)

Research only — not financial advice. No buy/sell language. SuccessContract
**still unmet** — `nested_contract_met: false`; no promotion.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v1` + `liq_v1` / relative / h1 / CSE |
| Snapshot | split-adjusted (`bb49b183b83585a2…`) |
| Models | `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Nested | 3 folds × seeds 0,1,2 (requested) |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-fp-liq` |
| Post-process | `/tmp/cpu-post-rel-h1-fp-liq` |
| Summary JSON | `cpu_exhaust_rel_h1_fp_liq_summary.json` |

Combined lever: W1 feature pack + W2 universe filter (`UNIVERSE_FILTER_LIQ_V1_SPEC.md`,
`FEATURE_PACK_V1_SPEC.md`).

Sample count after filter + fpv1 enrich: **32 535** rows (same as liq_v1-only).

---

## Nested RankIC vs frozen champions and single-lever runs

| Model | Frozen RankIC | fpv1 only | liq_v1 only | fp+liq | Δ vs frozen |
|---|---:|---:|---:|---:|---:|
| **`xgb_two_stage`** | **0.2861** | 0.2854 | n/a | n/a | — |
| `hgb_two_stage` | 0.2816 | 0.2809 | n/a | n/a | — |
| `double_ensemble_native` | 0.2566 | 0.2510 | 0.1813* | 0.1779* | **−0.0787** |

\*Partial nested (2/3 folds); xgb/hgb fail on all liq_v1 matrices.

Frozen selective baseline: xgb **74 emits / 0.770 prec / LCB 0.681**.
Frozen cost champion: DE persist **+0.49%** net@112.

### Headline

- **Combined matrix inherits liq_v1 kill.** Feature pack does not rescue the
  collapsed universe; xgb/hgb still cannot train.
- **No RankIC challenger.** Best fp+liq RankIC (DE 0.1779) is **0.1082 below**
  frozen xgb 0.2861 — worse than liq_v1-only DE (0.1813).
- fpv1-only showed mild RankIC regression (−0.0007); adding liq_v1 dominates
  with catastrophic sample loss — not a viable combined matrix ID for W5.
- **Selective: 0 emits** (contract **false**). **Cost best: −0.27%** net@112
  (DE `min_hold_5_top_bottom_10`); no persistence flip.

---

## W1 + W2 materiality

| Threshold | Fired? | Evidence |
|---|---|---|
| RankIC +0.005 | **No** | best Δ −0.1082 vs frozen |
| net@112 +0.10 pp | **No** | best −0.27% vs frozen DE +0.49% |
| Selective emits 2× | **No** | 0 vs 74 |
| W2 kill (universe collapse) | **Yes** | same 32535-row ceiling as liq_v1-only |

**Verdict:** fp+liq combo **killed**. Do not merge as new matrix for search.
Retire liq_v1 preset unless thresholds are relaxed in a new manifest.

---

## Selective gates (90% contract)

**NOT MET.**

| Model | Contract | Precision | LCB | Emits |
|---|:---:|---:|---:|---:|
| `xgb_two_stage` | n/a | n/a | n/a | n/a |
| `hgb_two_stage` | n/a | n/a | n/a | n/a |
| `double_ensemble_native` | **false** | — | — | **0** |

---

## Cost engineering @112 bps (DE only)

| Model | Best variant | Net | Sessions |
|---|---|---:|---:|
| `double_ensemble_native` | `min_hold_5_top_bottom_10` | **−0.27%** | 78 |
| `double_ensemble_native` | `persistence_exit_10_top_bottom_05` | −0.66% | 78 |

vs liq_v1-only best −0.40%; vs fpv1-only DE persist +0.53% — combined matrix
strictly worse on both levers.

---

## Promotion contract

**Contract: NOT MET.** Frozen RankIC champion (`xgb_two_stage` 0.2861) and
split-adjusted cost champion (DE persist +0.49%) **retained**. No
`forecast_points`. Not wired to `live_shadow`.
