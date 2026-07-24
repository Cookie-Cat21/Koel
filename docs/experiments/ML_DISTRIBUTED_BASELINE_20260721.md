# Distributed hybrid baseline — 2026-07-21

**Status:** contract not met  
**Dataset:** frozen `hybrid_daily_bars` snapshot  
**Snapshot SHA-256:** `69071c0689be1a338e90c95755e28f063aed69552cb75ee6f120d3fb3ea1a24d`

> Protocol audit: this v1 run predicts cross-sectionally demeaned
> outperformance, not absolute direction. Its repeatedly inspected folds are
> exploratory development evidence, not confirmatory evidence.

## Dataset

- 916,804 bars
- 200 symbols
- 2000-01-03 through 2026-07-16
- 869,912 Yahoo research bars
- 46,892 official CSE bars
- Windows crossing unresolved one-session moves over 50% were quarantined

## Frozen protocol

- Horizon: one trading session
- Six chronological outer folds
- 126-session calibration partition per fold
- 42-session test partition per fold
- Five-session embargo
- 63-session final lockbox (not evaluated)
- Minimum per-symbol history: 252 sessions
- Models: logistic, HGB large-move training, XGBoost large-move training
- Ensemble: equal score mean
- Gate threshold: maximum calibration coverage at calibration precision ≥ 90%
- Aggregate metrics: test partitions only

Contract: test precision and one-sided 95% Wilson lower bound ≥ 90%, at
least 500 emits, 80 symbols, 1% coverage, 2/3 folds at ≥85%, and no symbol
over 5% of emits.

## Results

| Run | Precision | 95% LCB | Emits | Coverage | Symbols | Max symbol share | Stable folds | Contract |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| One seed | 0.8944 | 0.8629 | 322 | 0.0090 | 88 | 0.1801 | 6/6 | **FAIL** |
| Three-seed mean | 0.8765 | 0.8441 | 340 | 0.0095 | 87 | 0.1706 | 5/6 | **FAIL** |

Three-seed fold detail:

| Fold | Test rows | Emits | Coverage | Precision |
|---:|---:|---:|---:|---:|
| 0 | 5,408 | 47 | 0.0087 | 0.9574 |
| 1 | 5,981 | 52 | 0.0087 | 0.8654 |
| 2 | 6,132 | 16 | 0.0026 | 0.8750 |
| 3 | 6,202 | 42 | 0.0068 | 0.9524 |
| 4 | 5,917 | 79 | 0.0134 | 0.8734 |
| 5 | 6,048 | 104 | 0.0172 | 0.8173 |

## Decision

The exploratory nested result is close to 90% as a point estimate but does not
support a 90% claim. It fails precision, confidence bound, support, coverage,
and concentration requirements. Seed averaging did not improve generalization.

Do not inspect the final lockbox. The next valid development work is:

1. point-in-time corporate-action and ticker-history repair;
2. source/missingness masks and Yahoo-pretrain/CSE-fine-tune ablation;
3. calibration-only model weighting or stacking;
4. multi-horizon experiments on the same frozen nested protocol;
5. temporal-model comparison after the data gates pass.

Research only — not financial advice.
