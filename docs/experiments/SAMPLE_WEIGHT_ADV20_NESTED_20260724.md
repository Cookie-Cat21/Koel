# ADV20 sample-weight nested — relative/h1 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet** — no
selective 90% unlock; no promotion.

## Run identity

| Field | Value |
|---|---|
| Matrix | frozen / relative / h1 / CSE + `--sample-weight adv20` |
| Snapshot | split-adjusted (`fc4d730527d4821f…`) |
| Models | `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Nested | 3 folds × seeds 0,1,2 |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-advw` |
| Post-process | `/tmp/cpu-post-rel-h1-advw` |
| Summary JSON | `cpu_exhaust_rel_h1_advw_summary.json` |

Spec: `SAMPLE_WEIGHT_ADV20_SPEC.md`.

---

## Nested RankIC vs frozen h1 champions

Frozen baseline: `cpu_exhaust_rel_h1_summary.json` (same split snapshot, no
sample weight). Champion RankIC **0.2861** (`xgb_two_stage`).

| Model | Frozen RankIC | adv20 RankIC | Δ RankIC | Frozen net@112 (DE persist) | adv20 net@112 |
|---|---:|---:|---:|---:|---:|
| **`xgb_two_stage`** | **0.2861** | 0.2862 | **+0.0001** | −0.78% | −0.78% daily L/S |
| `hgb_two_stage` | 0.2816 | 0.2824 | +0.0008 | −0.88% | −0.89% |
| `double_ensemble_native` | 0.2566 | 0.2502 | **−0.0064** | **+0.49%** | **+0.45%** (`persistence_exit_10_top_bottom_05`) |

### Headline

- **No RankIC challenger.** adv20 xgb 0.2862 is **+0.0001** above frozen 0.2861
  — well under W1 materiality (+0.005). Within fold noise.
- DE persist +0.45% vs frozen +0.49% (**−0.04 pp**) — below W1 net@112 (+0.10 pp).
- DE RankIC regresses −0.0064 vs frozen — liquidity weighting hurts ensemble.

---

## W1 materiality thresholds (master plan)

| Threshold | Fired? | Evidence |
|---|---|---|
| RankIC **+0.005** | **No** | Best Δ = +0.0008 (hgb); xgb +0.0001 |
| net@112 **+0.10 pp** | **No** | DE persist −0.04 pp vs frozen +0.49% |
| Selective emits **2×** | **No** | xgb **0** emits (was 74); hgb 85 vs 86 |

**Verdict:** ADV20 sample-weight lever **exhausted / no unlock**. Frozen RankIC
champion retained.

---

## Selective gates (90% contract) — honesty vs frozen

**NOT MET** for any model.

| Model | Contract | Precision | LCB | Emits | vs frozen |
|---|:---:|---:|---:|---:|---|
| `xgb_two_stage` | false | — | — | **0** | 74 / 0.770 / 0.681 |
| `hgb_two_stage` | false | 0.706 | 0.619 | 85 | 86 / 0.755 / 0.676 |
| `double_ensemble_native` | false | — | — | 0 | 0 emits |

adv20 **regresses selective** vs frozen: xgb collapses to 0 emits; hgb LCB 0.619
vs frozen 0.676. Contract honesty: **still false**, no promotion path.

---

## Cost engineering @112 bps (adv20 shards)

Best: `double_ensemble_native` / `persistence_exit_10_top_bottom_05`
**+0.45%** net@112 — below frozen split-adjusted **+0.49%**.

---

## Lever status

**EXHAUSTED** — adv20 sample weight on frozen matrix does not clear W1
materiality; selective and cost both regress or flat. Champions unchanged.
SuccessContract **still unmet**.

Next serial levers: abs/h1 split nested + absolute selective denser grids;
fpv2+adv20 combo nested.
