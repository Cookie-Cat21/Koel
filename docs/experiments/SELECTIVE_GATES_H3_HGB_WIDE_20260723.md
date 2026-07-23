# Selective gates h3 hgb wide abs grid — 2026-07-23

Research only — not financial advice. No buy/sell language.

## Command

```bash
python3 -m koel.ml.selective_gates \
  '/tmp/cpu-exhaust-rel-h3/nested/*-hgb_two_stage.predictions.jsonl.gz' \
  --model hgb_two_stage \
  --output-dir /tmp/cpu-selective-h3-hgb-wide \
  --abs-score-grid 0.001,0.0025,0.005,0.0075,0.01,0.015,0.02,0.025,0.03,0.04,0.05,0.075,0.10,0.125,0.15,0.175,0.20,0.225,0.25,0.30,0.35,0.40,0.50,0.75,1.00,1.50,2.00,3.00
```

Artifact: `selective_gates_h3_hgb_wide_20260723.json`.

## Result

| Model | Horizon | Precision | LCB | Emits | Symbols | Coverage | Stable folds | Contract |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `hgb_two_stage` | 3 | 0.6813 | 0.5967 | 91 | 37 | 0.00493 | 0/3 | **false** |

The wider absolute-score grid selected the same practical near-miss as the prior
h3 postprocess: fold 1 only, 91 emits, precision 0.681, LCB 0.597. All
SuccessContract checks remain false, including emits, symbols, coverage,
fold-stability, and concentration caps.

## Verdict

No Goal A unlock. H3 selective gating remains exhausted for this matrix.
