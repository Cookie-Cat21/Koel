# Selective gate mining — 2026-07-23

Goal: chase the existing `SuccessContract` with calibration-only selective
gates on nested model scores, not larger models.

## Method

- Inputs: `/tmp/cpu-exhaust-rel-h1/nested/*-{model}.predictions.jsonl.gz`.
- Models: `xgb_two_stage`, `double_ensemble_native`, `hgb_two_stage`.
- Selector: each outer fold searches only its calibration partition, then the
  chosen threshold is applied to that fold's matching test partition.
- Coverage grid: `0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025,
  0.03, 0.04, 0.05, 0.075, 0.10, 0.125, 0.15`.
- Optional absolute `|score|` floors: `0.01, 0.025, 0.05, 0.075, 0.10,
  0.125, 0.15, 0.175, 0.20, 0.225, 0.25, 0.30, 0.35, 0.40, 0.50, 0.75, 1.0`.
- Final checks use the unchanged `SuccessContract`: precision and one-sided
  LCB must both be at least `0.90`; emits `>=500`; symbols `>=80`; coverage
  `>=0.01`; concentration caps unchanged.

Command:

```bash
mkdir -p /tmp/cpu-selective-gates
for model in xgb_two_stage double_ensemble_native hgb_two_stage; do
  python3 -m koel.ml.selective_gates \
    "/tmp/cpu-exhaust-rel-h1/nested/*-${model}.predictions.jsonl.gz" \
    --model "$model" \
    --output-dir /tmp/cpu-selective-gates
done
```

## Results

No gate met the offline contract.

| model | contract | precision | LCB | emits | symbols | coverage | max symbol | max session |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `xgb_two_stage` | false | 0.770270 | 0.681161 | 74 | 40 | 0.004222 | 0.094595 | 0.094595 |
| `hgb_two_stage` | false | 0.720930 | 0.635568 | 86 | 48 | 0.004906 | 0.081395 | 0.093023 |
| `double_ensemble_native` | false | null | null | 0 | 0 | 0.000000 | 0.000000 | 0.000000 |

Best near miss by precision LCB: `xgb_two_stage`.

- It selected a calibration-safe gate only on fold 1:
  threshold `0.225`, calibration precision `0.921568`, calibration LCB
  `0.836360`, requested coverage `0.01`, with score floor `0.225`.
- Test result from that fold was 74 emits / 57 hits = precision `0.770270`,
  LCB `0.681161`.
- Folds 0 and 2 had no calibration gate satisfying the calibration guard.

Conclusion: the 90% precision/LCB contract is not reachable offline with these
current nested scores under the predeclared selective grids.

Artifacts:

- `/tmp/cpu-selective-gates/xgb_two_stage.selective_gates.json`
- `/tmp/cpu-selective-gates/xgb_two_stage.selective_gates.md`
- `/tmp/cpu-selective-gates/double_ensemble_native.selective_gates.json`
- `/tmp/cpu-selective-gates/double_ensemble_native.selective_gates.md`
- `/tmp/cpu-selective-gates/hgb_two_stage.selective_gates.json`
- `/tmp/cpu-selective-gates/hgb_two_stage.selective_gates.md`

Research only — not financial advice.
