# Distributed ML 90% master plan

**Status:** execution foundation + local baseline complete; target not met  
**Primary goal:** selective CSE direction precision, not always-on accuracy  
**Compliance:** research signal only, always NFA

## 1. Success contract

“90%” means correctness **when the system emits**. It does not mean predicting
every symbol every day with 90% accuracy.

The development gate is fixed before model search:

| Requirement | Gate |
|---|---:|
| Test-only selective precision | ≥ 0.90 |
| One-sided 95% Wilson lower bound | ≥ 0.90 |
| Held-out emits | ≥ 500 |
| Distinct symbols | ≥ 80 |
| Eligible-row coverage | ≥ 1% |
| Stable outer folds | ≥ 2/3 at precision ≥ 0.85 |
| Largest symbol share of emits | ≤ 5% |

Calibration thresholds are selected inside each outer fold's calibration
partition. They are then frozen and applied once to that fold's test partition.
The final lockbox is excluded from all development folds.

The production claim requires a second independent pass on prospectively
recorded shadow forecasts. A development pass alone is not a promise of future
performance.

## 2. Current evidence and constraints

Read-only DB profile on 2026-07-21:

- `hybrid_daily_bars`: 916,804 rows, 200 symbols, 2000-01-03 to 2026-07-16.
- Yahoo research layer: 869,912 rows, 179 symbols; only 77 symbols start in 2000.
- Official CSE layer: 46,892 rows, 200 symbols, beginning 2025-07-18.
- Yahoo history contains 9,964 one-session moves over 20%, 1,629 over 50%,
  and 317 over 100%; unresolved cliffs cannot be treated as normal labels.
- Only 22 corporate actions are recorded, so long-history adjustment is incomplete.
- Financial extraction is now materially denser: 3,675 successful metrics rows
  and 1,809 usable YoY comparisons.
- Existing scored outcomes are mostly walk-forward shadow rows; there is no
  adequate prospective HPE result yet.

Existing research establishes the precision/coverage trade-off:

- Always-on direction plateau: about 59–60%.
- Moderate confidence gates: about 66–71%.
- Previous 90.3% HPE estimate: only about 0.5% coverage and selected on the
  same pooled OOS rows used for reporting.

The old HPE serving path also trains one horizon-1 panel model and reuses its
score for horizon 1/2/3/5 and absolute streams. It does not reproduce the
research configuration and cannot be used as proof.

## 3. Distributed architecture

```text
read-only Neon snapshot
        |
        v
immutable gzip JSONL + SHA-256 manifest
        |
        v
fold × model GitHub Actions matrix
        |
        +-- seeds averaged inside each worker
        +-- calibration predictions
        +-- test predictions
        |
        v
fan-in alignment by symbol/date/horizon
        |
        v
calibration-only threshold selection
        |
        v
test-only contract report
        |
        v
locked final test -> prospective shadow -> manual promotion
```

The initial matrix uses:

- Six chronological outer folds.
- `logistic`, `hgb_lmt`, and `xgb_lmt`.
- Three seeds per fold/model worker.
- A 63-session final lockbox.
- Five-session embargo (or the horizon when larger).
- Price-cliff quarantine for feature/label windows crossing unresolved >50%
  session moves.

Many Actions provide independent experiment compute and an ensemble. They do
not create shared GPU memory or synchronously train one giant model.

## 4. Execution phases

### Phase A — correctness foundation

- [x] Immutable, repeatable-read bar snapshot with SHA-256 verification.
- [x] Deterministic fold/model fan-out matrix.
- [x] Standard prediction artifact schema.
- [x] Fan-in model alignment and ensemble averaging.
- [x] Calibration-only gate selection.
- [x] Test-only precision, coverage, concentration and Wilson bound.
- [x] Reserved final lockbox.
- [x] Manual GitHub Actions workflow with no promotion or forecast writes.
- [x] Run the full six-fold local baseline and archive its honest failure.
- [ ] Create `ML_DATABASE_URL` using a SELECT-only Postgres role.
- [ ] Reproduce the baseline through the GitHub Actions matrix.

### Phase B — point-in-time data repair

1. Preserve raw snapshots; never overwrite source observations.
2. Reconstruct split/consolidation adjustments and quarantine unresolved cliffs.
3. Validate Yahoo ticker mappings, renames and stale/flat spans.
4. Add source and missingness masks; Yahoo and CSE are separate domains.
5. Define point-in-time universe membership to reduce survivorship bias.
6. Join filings by publication availability (plus one session), never merely
   by fiscal period end.
7. Add no-trade/liquidity eligibility and explicitly model flat sessions.
8. Produce a versioned data-quality report for every snapshot.

No deep model advances while unresolved data errors can manufacture labels.

### Phase C — distributed baseline ladder

Run all candidates at identical folds and coverage:

1. Majority, prior-return and regularized logistic controls.
2. Current HGB LMT baseline.
3. Tuned HGB, XGBoost and LightGBM classifiers/rankers.
4. Separate direction, magnitude and volatility targets.
5. CSE-only, naïvely pooled, and Yahoo-pretrain/CSE-fine-tune ablations.

A candidate survives only if it improves at matched coverage across most folds,
not just in the pooled average.

### Phase D — larger temporal model

Use a self-hosted or GitHub larger GPU runner:

- Patch/temporal encoder, approximately 5–30M parameters.
- 64/128/256-session windows.
- Symbol and sector embeddings.
- Source, missingness, liquidity and regime masks.
- Multi-head outputs for direction, magnitude and volatility.
- Masked-history pretraining on cleaned Yahoo bars.
- Fine-tuning and model selection on official CSE-domain folds.

Generic time-series foundation models are benchmarks or feature generators,
not assumed winners. A billion-parameter model is not justified by this panel.

### Phase E — ensemble, calibration and distillation

1. Combine only out-of-fold predictions from surviving tree and temporal models.
2. Train the correctness/meta-label model on calibration predictions only.
3. Gate on calibrated probability, model disagreement, data quality and liquidity.
4. Publish precision-risk curves at 0.5%, 1%, 2%, 5% and 10% coverage.
5. If the ensemble is expensive, distill its soft predictions into one smaller
   serving model without touching the lockbox.

### Phase F — final and prospective validation

1. Freeze code, feature schema, dataset SHA, model settings and gate.
2. Evaluate the final lockbox exactly once.
3. If it fails, record the failure; do not retune against it.
4. Emit append-only shadow predictions prospectively.
5. Score every due outcome automatically.
6. Require the same precision, support, coverage and concentration contract.

### Phase G — production integration

- Persist exact model weights, preprocessors, calibrators and feature schema.
- Use trading-session horizons end-to-end.
- Train and serve the same per-horizon or multi-head architecture.
- Fail closed on stale bars, missing features or schema mismatch.
- Keep a manual promotion step and automatic rollback/degraded state.
- Never label Yahoo-derived history as official CSE truth.

## 5. GitHub Actions safety

`ml-train-v2` is manual and read-only:

- Uses `ML_DATABASE_URL`; it does not fall back to the production workflow secret.
- Exports one snapshot, then workers download the same immutable artifact.
- Workers receive no database credential.
- Every shard records the run ID and snapshot hash.
- Aggregation fails on missing models, duplicate shards, mismatched hashes or
  inconsistent ground truth.
- It uploads reports but never migrates, promotes models or writes forecasts.

Standard runners handle the tree baseline. A temporal model should use a
GitHub GPU larger runner or a self-hosted 24–48 GB GPU runner. Synchronous
multi-GPU training belongs on one self-hosted node/cluster, not unrelated
ephemeral Actions workers.

## 6. Anti-overfitting rules

- Predeclare models, folds, seeds, metrics and gates per run.
- Selection uses calibration partitions only.
- Test and lockbox labels never choose thresholds or features.
- Report every attempted family, including failures.
- Use block resampling by market session and symbol for uncertainty checks.
- Limit symbol and sector concentration.
- A new search after lockbox exposure requires a new prospective lockbox.
- More parallel jobs are not evidence; only untouched outcomes are evidence.

## 7. Stop/go decisions

| Observation | Decision |
|---|---|
| Clean hybrid does not beat CSE-only/tree controls | Stop scaling model size; repair data/features |
| Precision reaches 90% only below 1% coverage | Do not claim contract success; optimize coverage |
| One sector/symbol dominates emits | Reject candidate |
| Point estimate ≥90%, lower bound <90% | Continue shadow evidence; no 90% claim |
| Nested test passes, lockbox fails | Record failure and return to research |
| Lockbox and prospective shadow pass | Eligible for manual product review |

## 8. Definition of done

The goal is reached only when:

1. The exact contract passes on nested test partitions.
2. The frozen candidate passes its untouched lockbox.
3. The same frozen candidate passes prospective shadow outcomes.
4. Reproduction from snapshot SHA and commit SHA yields the same report.
5. Product language remains selective, research-only and not financial advice.

Until all five hold, the correct status is **research in progress**, regardless
of model size or the best observed point estimate.
