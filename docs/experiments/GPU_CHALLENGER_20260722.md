# GPU challenger ladder — RTX 3050, 2026-07-22

Status: **in progress / interim report**. `qlib_tra` and `master` have
completed their horizon-1, three-fold evaluation (or hit a hard blocker, in
`master`'s case). `kronos_features` is still running at the time of this
write-up (see §5) — this document will be updated with final numbers once it
finishes; do not treat its section below as final.

## 0. Environment

- Machine: Windows 11, NVIDIA GeForce RTX 3050 **6GB Laptop GPU** (6.44GB
  reported by `torch.cuda.get_device_properties`), not the 16–24GB assumed by
  `docs/factory/QLIB_CHALLENGER_MASTER_PLAN.md`/`ML_DISTRIBUTED_90_MASTER_PLAN.md`
  — every hyperparameter below is scaled down accordingly (see §4).
- Python 3.12.10, isolated venv at `E:\koel-ml\.venv312` (kept off the C:
  drive, which had <2GB free for most of this session).
- `torch==2.5.1+cu121` (CUDA build, verified with a real on-device matmul),
  `pyqlib==0.9.7` pinned to Qlib release commit
  `da920b7f954f48ab1bb64117c976710de198373e`, `lightgbm==4.7.0`,
  `einops==0.8.1`, `huggingface_hub==0.33.1`, `safetensors==0.6.2`.
- Snapshot: `python -m koel.ml.snapshot export --dataset hybrid`
  - `bars_sha256`: `dc7de31d5c9ac46f17d878aee89676306da1959ff0b006badc7020a4a00f1da7`
  - `fundamentals_sha256`: `ce153d84cac292ad124478c18dc83467ddaeee2e9842dc12c276386ac06621a2`
  - **composite snapshot SHA** (what `live_shadow.py`-style model_version
    identity would use): `2da15d82f618a6532bcc09199887e6a09b3412079729263c41eba1ac42f28785`
  - 917,087 rows, 292 symbols (47,175 CSE + 869,912 Yahoo), 2000-01-03 through
    2026-07-21.

### Environment problems found and fixed along the way

1. **Neon pooled connection silently kills the snapshot export.**
   `export_bar_snapshot` opens an async server-side (`DECLARE CURSOR`-style)
   streaming cursor. Neon's pooled endpoint
   (`...-pooler.c-3.us-east-2.aws.neon.tech`) runs PgBouncer in transaction
   -pooling mode, which does not support server-side cursors — the export
   died twice after ~10MB with `server closed the connection unexpectedly`
   and no earlier error. Switching `ML_DATABASE_URL` to the direct
   (non-pooled) endpoint fixed it outright. **This is a real, reusable
   finding for anyone re-running this export**, not specific to this
   machine.
2. **Windows `ProactorEventLoop` incompatible with `psycopg`'s async pool.**
   `asyncio.run()`'s default loop on Windows can't run psycopg async mode
   (`Psycopg cannot use the 'ProactorEventLoop'...`). Worked around locally
   with a tiny wrapper forcing `asyncio.WindowsSelectorEventLoopPolicy()`
   before calling `koel.ml.snapshot.main()` — not a repo change, since
   production runs on Linux.
3. **OpenBLAS `Memory allocation still failed after 10 retries` crash.**
   First `distributed_worker` invocation for `qlib_tra` fold 0 died
   immediately with this error despite 13GB+ free physical RAM. Root cause
   was Windows' small pagefile (`FreeVirtualMemory` was ~5GB even with RAM
   free) combined with unbounded OpenBLAS/OMP/MKL thread counts. Fixed by
   capping `OPENBLAS_NUM_THREADS`/`OMP_NUM_THREADS`/`MKL_NUM_THREADS`/
   `NUMEXPR_NUM_THREADS=4` in the run environment.
4. **`_tra_frame`'s original `pd.concat({"feature": ..., "label": ...})`
   construction roughly doubled peak memory** versus building one float32
   array directly with `MultiIndex` columns up front. At hybrid-dataset
   scale (fold 0's combined fit+valid+test frame is 454,722 rows × 91
   columns) the concat path failed with `Unable to allocate 316. MiB` even
   though machine-level memory looked fine — same virtual-memory-commit
   constraint as #3, aggravated by concat's internal block-manager copy.
   Fixed in `koel/ml/gpu_challengers.py::_tra_frame` (see diff); this made
   `qlib_tra` viable at full scale. The equivalent fix was **not** applied
   in time to `master`'s windowing path — see §3.

## 1. Protocol

Matches the mission spec exactly: three chronological official-CSE
development folds (`--outer-folds 3`), `--horizon 1`, `--seeds 0,1,2`,
`--target relative`, `--evaluation-domain cse`, `--max-flat-fraction 0.40`.
Training itself uses the full hybrid (CSE+Yahoo) universe per the existing
domain-weighted-training design already used by `*_domain` CPU challengers;
`--evaluation-domain cse` restricts scoring to CSE rows only. Pooled test
set across the three folds: **16,779 rows / 122 sessions** — this exactly
matches the row/session count reported for the existing CPU baselines in
`docs/experiments/QLIB_CHALLENGER_20260721.md` and PR #94's description, so
the comparison below is apples-to-apples.

No hyperparameter here was tuned against any fold's test labels. Each model
below has exactly one predeclared config (stated per model), varied only by
`seed`.

## 2. `qlib_tra` — TRA (RNN backbone + router), pinned Qlib 0.9.7

**Verdict: rejected.** Below the DoubleEnsemble baseline (RankIC 0.2526) on
every fold and pooled, and its top/bottom spread could not even be computed
(see below) — disqualifying on its own regardless of RankIC.

Config (predeclared, scaled down from Qlib's Alpha360 example for a 6GB GPU
and CSE's much smaller universe): RNN(GRU) backbone, `hidden_size=64`,
2 layers, attention; TRA router, `num_states=3`, `hidden_size=16`,
`transport_method="router"`, `seq_len=20`, `n_epochs=30` (`early_stop=8`,
`max_steps_per_epoch=100`), `lr=1e-3`, `lamb=0.5`, `rho=0.99`, `alpha=1.0`.

| Fold | n (test rows) | sessions | RankIC | Balanced accuracy | MCC |
|---|---|---|---|---|---|
| 0 | 5,581 | 40 | 0.1373 | 0.5444 | 0.0905 |
| 1 | 5,552 | 41 | 0.1298 | 0.5002 | 0.0112 |
| 2 | 5,646 | 41 | 0.1435 | 0.5423 | 0.0968 |
| **Pooled** | **16,779** | **122** | **0.1369** | **0.5284** | **0.0617** |

Baseline for comparison (native DoubleEnsemble, same protocol, from PR #94):
RankIC 0.2526, balanced accuracy 0.5763, MCC 0.1509.

**Cost-adjusted top/bottom spread (fraction 0.10) at 112bps and 30bps:
`None` for every fold and pooled.** `cost_adjusted_top_bottom_spread` skips
any session where scores are tied at the decile boundary; every session in
every fold was skipped this way. Inspecting raw predictions confirmed the
cause: many sessions have **literally identical scores across most/all
symbols** (e.g. `-0.00606988122065862` repeated across multiple distinct
symbols on the same date). The most likely explanation is that the TRA
router's `state` input (historical prediction-error memory) is effectively
all-zero for most test-partition rows — since this three-fold protocol
never runs an explicit memory warm-up pass over the test partition before
scoring it — collapsing the router's per-sample routing decision to the
same expert for most of a session's names, and hence very little
within-session cross-sectional differentiation. This is a real limitation
of this adapter's current test-time protocol, not a training bug (training
itself converges normally and RankIC is clearly non-zero), and would need a
calibration-partition memory warm-up (mirroring what `MTSDatasetH`'s
`memory_mode="daily"` intends) to fix properly — flagged as follow-up work,
not attempted here to keep this run inside the predeclared-config,
no-post-hoc-tuning contract.

Horizon-5 run: **not attempted** — the model did not clear the promotion
bar at horizon 1, and the mission only asks for horizon-5 on survivors.

Wall-clock: ~15–20 minutes/fold on the RTX 3050.

## 3. `master` — MASTER (market-gated dual attention), pinned MIT revision

**Verdict: blocked (not evaluated) — a real bug in this adapter, not a
model-quality finding.** All three folds failed identically:

```
numpy._core._exceptions._ArrayMemoryError: Unable to allocate 2.55 GiB for
an array with shape (375389, 20, 91) and data type float32
```

Root cause: `_windowed_by_symbol`/`_segment_tensors` in
`koel/ml/gpu_challengers.py` materializes the **entire** fit/valid/test
segment as one dense `(rows, seq_len, features)` float32 array before
training starts. At hybrid-dataset scale (fold 0's fit segment alone is
375,389 rows), that's ~2.5GB for one segment, on top of whatever the
Windows virtual-memory-commit ceiling already described in §0.3/§0.4 leaves
available — it failed consistently, not intermittently, across all three
folds.

This is architecturally the same class of problem already fixed for
`qlib_tra`'s frame construction (§0.4), but the fix there (avoid one large
eager copy; let `MTSDatasetH` construct windows lazily per batch) doesn't
directly transfer, since MASTER's training loop here is hand-rolled rather
than going through Qlib's own dataset machinery. The correct fix is to
build each day's window batch on demand inside the training loop (as
`MTSDatasetH.__iter__` does) instead of pre-stacking the whole segment —
not done in this pass; time was redirected to writing up and shipping this
interim report instead of iterating further on it. **Recommended follow-up**
before re-attempting `master`: rewrite `_segment_tensors`/the epoch loop to
build one day's `(symbols_that_day, seq_len, features)` batch at a time
from `_windowed_by_symbol`'s dict (already keyed by `(symbol, date)`,
so this is a scoping change, not a redesign), and cap the smoke-tested
default config (this report's `d_model=64`) rather than only relying on
synthetic-data unit tests to catch scale problems.

Config used (never got past adapter smoke tests to a real fold result):
`d_model=64`, `t_nhead=4`, `s_nhead=2`, `seq_len=20`, `dropout=0.1`,
`beta=5.0`, `n_epochs=30`, `lr=1e-3`, trailing 5-column
`MARKET_CONTEXT_NAMES` block as the feature-gate input.

## 4. `kronos_features` — frozen Kronos-mini forecast features + existing LightGBM

**Status at time of writing: fold 0 of 3 still running (started after
`master`'s three failures).** Per-row benchmark: ~19ms/row (`sample_count=8`,
`pred_len=1`) on the RTX 3050, and fold 0's combined fit+valid+test row
count is in the same ~375k–455k range as `qlib_tra`/`master` above, i.e.
roughly ~2 hours for this one fold. **This section will be replaced with
real numbers once all three folds finish — do not cite the "in progress"
state as a result.**

Design (implemented and unit-tested on synthetic data ahead of this run):

- Kronos is used **only** as a frozen feature generator — no fine-tuning,
  no gradient ever reaches it.
- `Sample.x` only carries engineered features, not raw OHLCV bars, so a
  synthetic daily price path is reconstructed per sample from its own
  `log_price`/`ret_1d`/`ret_5d`/`ret_20d`/`ret_60d`/`liquidity_20d`/
  `vol_spike`/`range_20d` features (geometric interpolation between the
  known trailing-return anchor points) — a documented approximation, not
  the true history. Kronos's own input normalization
  (`(x - x_mean) / (x_std + 1e-5)`) means only the *relative shape* of this
  reconstruction matters, not its absolute scale.
- `KronosPredictor.predict()` only returns the *mean* of its internal
  Monte-Carlo forecast samples, which throws away the distribution needed
  for quantile-width/p(up) — so this adapter reimplements
  `auto_regressive_inference` (`_kronos_sample_paths`, copied from the
  vendored `kronos.py` minus its final `np.mean` reduction) to keep every
  sampled path.
- Three features appended per row: median forecast return, IQR
  (quantile width) of forecast returns across Monte-Carlo samples, and
  p(up) (fraction of samples forecasting a positive return). These feed
  the **existing, unmodified** `predict_qlib_lightgbm` challenger.
- Checkpoints (both pinned to the public revision current at the time of
  this run — **not independently re-pinned beyond what Hugging Face Hub's
  `from_pretrained` resolved**, a gap worth tightening for full
  reproducibility):
  - Tokenizer `NeoQuasar/Kronos-Tokenizer-2k`, HF snapshot
    `26966d0035065a0cae0ebad7af8ece35bc1fb51c`
  - Model `NeoQuasar/Kronos-mini`, HF snapshot
    `f4e68697d9d5aed55cef5c96aabc3376bcad9f81` (4.1M params)
- **Contamination boundary**: both checkpoints were pretrained on public
  data through June 2024. This adapter's use is only valid evidence for
  evaluation windows strictly after that date — the official-CSE
  development folds used here satisfy that (fold test windows fall in
  2025–2026 per the `as_of` dates observed in the `qlib_tra` artifacts
  above), but this must be re-checked if the fold windows are ever changed.

## 5. Summary table (interim)

| Model | RankIC (pooled) | Balanced acc. | MCC | Spread @112bps | Verdict |
|---|---|---|---|---|---|
| DoubleEnsemble (baseline, PR #94) | 0.2526 | 0.5763 | 0.1509 | net -0.69% | (existing) |
| `qlib_tra` | 0.1369 | 0.5284 | 0.0617 | not computable (tied scores) | **rejected** |
| `master` | — | — | — | — | **blocked** (OOM bug, §3) |
| `kronos_features` | pending | pending | pending | pending | **pending** |

## 6. Honest scope notes

- Neither `qlib_tra` nor `master` beat the baseline (one on the numbers, one
  never got a number) — this report does not claim any challenger here is
  promising against DoubleEnsemble.
- No hyperparameter was tuned against test-fold labels for any model in
  this document.
- No new live policy ID has been registered; `koel/ml/live_shadow.py` and
  `POLICY_MODELS`/`POLICY_SELECTIVE`/`POLICY_PRESSURE` were not touched.
  The proposed IDs (`shadow_policy_rank_tra_v1`,
  `shadow_policy_rank_master_v1`, `shadow_policy_rank_kronos_v1`) remain
  exactly as pinned in `koel/ml/challenger_catalog.py` and are not
  eligible for promotion given the results above.
- This document will be updated in place once `kronos_features` finishes;
  the git history / PR comments record when that update landed.
