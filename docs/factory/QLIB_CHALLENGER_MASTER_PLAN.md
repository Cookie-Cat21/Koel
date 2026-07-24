# Qlib + open challenger master plan

**Status:** Phase 1 implementation active  
**Primary goal:** stable CSE ranking and calibrated direction skill  
**Qualification:** official-CSE chronological and prospective outcomes only

## 1. Shared contract

Every challenger must consume the same immutable CSE snapshot and emit the
existing `Prediction` schema. No model-specific test filtering is allowed.

Primary metrics:

- equal-session mean daily RankIC;
- balanced direction accuracy and MCC on non-flat outcomes;
- Brier score and fixed-bin ECE;
- selective precision/coverage with flat emits counted as misses;
- top/bottom spread, turnover and net return under versioned CSE costs;
- symbol/session/sector concentration and block confidence intervals.

Offline promotion gates:

- mean RankIC ≥0.03 with a positive one-sided session-block lower bound;
- balanced accuracy ≥0.53 and MCC ≥0.05 with positive lower bounds;
- positive Brier skill;
- positive post-cost spread in at least three of four chronological blocks;
- no integrity, source, target-date or concentration failures.

Offline success makes a challenger eligible for an immutable prospective
policy ID. It does not make it user-facing.

## 2. Data layer

Source of truth remains `koel/ml/snapshot.py`.

The Qlib adapter exports one deterministic CSV per CSE instrument:

`date,open,high,low,close,volume,factor,change`

Rules:

- `.N0000` / `.X0000` ordinary company shares only;
- stable CSE symbol mapping;
- duplicate symbol/date rows rejected;
- explicit calendar and instrument manifests;
- snapshot and every output file hashed;
- `factor=1` is marked unadjusted and cannot qualify a tradable claim;
- Yahoo history may train but official-CSE periods alone qualify performance.

Qlib 0.9.7 is the pinned native integration target:

- package: `pyqlib==0.9.7`;
- release commit:
  `da920b7f954f48ab1bb64117c976710de198373e`;
- license: MIT.

Native Qlib binary conversion runs in an isolated workflow. Koel does not
vendor Qlib.

## 3. Challenger ladder

| Stage | Challenger | Upstream pin | License | Proposed policy ID |
|---|---|---|---|---|
| 1 | Qlib-style LightGBM regression/ranking | Qlib 0.9.7 | MIT | `shadow_policy_rank_qlib_lgb_v1` |
| 1 | Qlib DoubleEnsemble | Qlib 0.9.7 | MIT | `shadow_policy_rank_qlib_de_v1` |
| 2 | TRA | Qlib 0.9.7 | MIT | `shadow_policy_rank_tra_v1` |
| 3 | MASTER | `de8f585...` | MIT | `shadow_policy_rank_master_v1` |
| 3 | StockMixer | `cce1359...` | no detected license | blocked pending permission |
| 3 | Multitask Stockformer | `0a4f78b...` | no detected license | blocked pending permission |
| 4 | Kronos mini/base | `67b630e...` | MIT | `shadow_policy_rank_kronos_v1` |
| Later | TLOB | upstream MIT | MIT | blocked until genuine CSE L2 event data |

Missing-license repositories may be studied and reproduced from the paper, but
their source is not copied or distributed.

## 4. Implementation phases

### Phase 1 — common data and metrics

- [x] Immutable Koel bars + filings snapshot.
- [x] Qlib-compatible deterministic CSV/calendar/instrument export.
- [x] Native Qlib binary conversion and provider smoke.
- [x] Average-rank Spearman implementation with tie handling.
- [x] Balanced accuracy, MCC, Brier and ECE.
- [x] Top/bottom spread, turnover and cost stress.
- [x] Unified challenger report JSON/Markdown.

### Phase 2 — CPU parity challengers

- [x] Qlib-parameter LightGBM rank/regression baseline.
- [x] Native DoubleEnsemble concept approximation.
- [x] Exact Qlib LightGBM adapter and fold-0 smoke.
- [x] Exact Qlib DoubleEnsemble adapter and fold-0 smoke.
- [x] Isolated exact three-fold Qlib workflow.
- [ ] Complete and review the exact three-fold workflow artifact.
- [ ] Compare native and Qlib outputs on identical fold keys.
- [ ] Add new prospective policy IDs only after offline gates pass.

Initial three-fold results are recorded in
`docs/experiments/QLIB_CHALLENGER_20260721.md`. RankIC and direction metrics
are promising, but both candidates remain blocked because the 112 bps cost
stress is negative and the export is not yet corporate-action adjusted.

### Phase 3 — GPU sequence challengers

- [x] TRA through pinned Qlib -- implemented (`koel/ml/gpu_challengers.py`
      ::predict_qlib_tra), evaluated three-fold h1 on an RTX 3050
      2026-07-22: RankIC 0.1369 pooled, below the DoubleEnsemble baseline
      (0.2526); rejected. See
      `docs/experiments/GPU_CHALLENGER_20260722.md`.
- [x] MASTER pinned MIT adapter -- implemented and unit-tested, but blocked
      at full hybrid-dataset scale by an OOM bug in this adapter's window
      construction (all three folds failed identically); not yet evaluated.
      See `docs/experiments/GPU_CHALLENGER_20260722.md` section 3 for the
      root cause and recommended fix.
- [ ] StockMixer/Stockformer clean-room adapters only after license clearance.
- [ ] Shared 64/128/256-session tensor and missingness masks -- **deviation**:
      implemented with `seq_len=20` for both TRA and MASTER instead, scaled
      down for the RTX 3050's 6GB VRAM and CSE's much smaller instrument
      universe versus this doc's original 16-24GB GPU assumption.
- [x] Same prediction artifact and evaluation contract -- both adapters
      dispatch through the existing `ALLOWED_MODELS`/`_fit_predict_one`/
      `Prediction` schema unchanged.

### Phase 4 — foundation feature challenger

- [x] Kronos mini/base frozen checkpoint -- Kronos-mini implemented
      (`koel/ml/gpu_challengers.py::predict_kronos_features`, vendored
      architecture in `koel/ml/vendor/kronos/`); full three-fold h1
      evaluation in progress as of 2026-07-22, see
      `docs/experiments/GPU_CHALLENGER_20260722.md` section 4 for interim
      status -- update this line once that run completes.
- [x] Record checkpoint and pretraining cutoff hashes -- HF snapshots
      `f4e68697d9d5aed55cef5c96aabc3376bcad9f81` (Kronos-mini) and
      `26966d0035065a0cae0ebad7af8ece35bc1fb51c` (Kronos-Tokenizer-2k);
      June 2024 pretraining cutoff documented as a contamination boundary.
- [x] Use median return, quantile width and p(up) as ranker features (fed
      into the existing, unmodified LightGBM challenger) -- upstream
      embeddings were not additionally pursued in this pass.
- [x] Do not treat "93% RankIC improvement" as accuracy -- this report makes
      no such claim; results are reported as RankIC/BA/MCC/cost-adjusted
      spread only.

### Phase 5 — prospective policy tournament

- Each passed challenger gets an immutable `policy_id`.
- Each daily fit gets a snapshot/code-bound model instance.
- Outcomes aggregate by fixed policy across instances.
- Policies retrain automatically after each matured CSE session.
- Standards can mark `review_eligible`; promotion remains separately approved.

## 5. Compute split

| Work | Runner |
|---|---|
| Export, metrics, LightGBM | standard CPU Actions |
| Qlib DoubleEnsemble | larger CPU or bounded standard worker |
| TRA / MASTER / StockMixer / Stockformer | one 16–24 GB GPU |
| Kronos mini/base inference | GPU preferred; CPU benchmark permitted |

Deep models do not enter the daily live workflow until training time is below
the post-close window and offline gates pass.

## 6. Stop rules

- No repeated tuning against the same development outcomes.
- No policy ID reuse after feature/config changes.
- No 90% claim from selected stocks, selected sessions or another metric.
- No LOB architecture on aggregate bid/ask totals.
- No tradable-return claim while corporate actions, execution prices, fees or
short availability are unresolved.

Research only — not financial advice.
