# Selective disagreement gates — Goal A (2026-07-24)

Research only — not financial advice. **SuccessContract still unmet** — no
selective 90% unlock; no promotion.

## Harness

Module: `koel/ml/selective_disagreement.py`

- Aligns nested prediction shards on `(outer_fold, partition, symbol, as_of)`.
- Primary score = first model in `--models` (default `xgb_two_stage`).
- Disagreement = cross-model `stdev` (default) or `range` (max − min).
- Searches predeclared grids on **calibration only**:
  - coverage `{0.005, 0.01, 0.02, 0.05, 0.10}`
  - absolute primary-score floors (same grid as `selective_gates`)
  - max disagreement `{0.02, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30}`
- Applies per-fold chosen gate to test; evaluates `SuccessContract` via
  `selective_gates._contract_checks`.

## Data

| Field | Value |
|---|---|
| Matrix | feature pack v2 / relative / h1 |
| Nested dir | `/tmp/cpu-exhaust-rel-h1-fpv2/nested` |
| Models | `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Folds | 3 × seeds 0,1,2 |
| Output | `/tmp/cpu-selective-disagree-fpv2` |

Command:

```bash
python3 -m koel.ml.selective_disagreement \
  --nested-dir /tmp/cpu-exhaust-rel-h1-fpv2/nested \
  --models xgb_two_stage,hgb_two_stage \
  --output-dir /tmp/cpu-selective-disagree-fpv2/two_model
```

Baseline single-model gate (same shards, no disagreement filter):

```bash
python3 -m koel.ml.selective_gates \
  /tmp/cpu-exhaust-rel-h1-fpv2/nested --model xgb_two_stage \
  --output-dir /tmp/cpu-selective-disagree-fpv2
```

---

## Aggregate test metrics

| Variant | Contract | Precision | LCB | Emits | Symbols | Coverage | Stable folds |
|---|:---:|---:|---:|---:|---:|---:|---:|
| xgb single-model (`selective_gates`) | **false** | 0.762 | 0.688 | 105 | 52 | 0.0058 | 0/3 |
| xgb+hgb, stdev disagree | **false** | **0.779** | **0.693** | 77 | 39 | 0.0042 | 0/3 |
| xgb+hgb+DE, stdev disagree | **false** | 0.770 | 0.681 | 74 | 39 | 0.0041 | 0/3 |
| xgb+hgb, range disagree | **false** | 0.750 | 0.661 | 76 | 45 | 0.0042 | 0/3 |

Contract honesty: **all checks false** for every variant. Point precision and
LCB remain far below the 0.90 floor. Disagreement filtering trades emits for a
modest precision lift (+1.7 pp vs single-model xgb on the 2-model stdev run)
but does **not** approach Goal A.

---

## Fold-level notes

**2-model stdev (best disagreement run):**

| Fold | Cal gate | Score thr | Max disagree | Test emits | Test precision |
|---|:---:|---:|---:|---:|---:|
| 0 | none | — | — | 0 | — |
| 1 | coverage_abs_floor @2% | 0.225 | 0.05 | 77 | 0.779 |
| 2 | none | — | — | 0 | — |

Folds 0 and 2 found **no** calibration gate meeting the 90% / LCB≥0.80
viability filter once disagreement is required. All test emits come from fold 1 —
fold stability and emit-day checks fail.

**Single-model xgb baseline:** fold 1 cal gate hits 91.0% precision (89 cal
emits); test fold 1 precision 76.2% with 105 total emits across folds (folds 0
and 2 also emit zero).

---

## Verdict

Multi-model disagreement gating is a useful research harness (calibration-only
selection, no test peeking) but **does not unlock Goal A** on fpv2 nested
relative/h1. Best near-miss: **0.779 precision / 0.693 LCB @ 77 emits**
(xgb+hgb stdev) vs single-model **0.762 / 0.688 @ 105 emits**.

Champions unchanged. SuccessContract **still unmet**.
