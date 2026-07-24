# ML live shadow runbook

Prospective CSE prediction evidence without Telegram or dashboard forecasts.

## Safety boundary

The live shadow path writes:

- normalized live inputs to existing market tables;
- final ordinary-share closes to `daily_bars` / `hybrid_daily_bars`;
- predictions only to `forecast_outcomes`.

It never writes `forecast_points`, never evaluates alert rules, and never sends
Telegram messages.

Use a scoped `ML_SHADOW_DATABASE_URL` GitHub secret. It needs the existing
application role's read/write access to market capture tables,
`daily_bars`, `hybrid_daily_bars`, and `forecast_outcomes`. The read-only
`ML_DATABASE_URL` used by distributed training is intentionally separate.
Until the scoped role is configured, the workflow falls back to the existing
`DATABASE_URL` application secret so prospective capture does not stop.

## Scheduled workflow

`.github/workflows/ml-live-shadow.yml` runs at 14:45 Asia/Colombo on weekdays:

1. Capture and persist the final board, indexes, sectors, market summary and
   stable top-25 ordinary-share order books.
2. Export an immutable bars + publication-safe filings snapshot.
3. Train the frozen shadow challenger and emit:
   - all eligible-company absolute direction from three fixed policies
     (`xgb_two_stage`, `hgb_two_stage`, `xgb_domain`);
   - top-0.5% confidence challenger;
   - displayed-book + signed-volume pressure overlay;
   - Loop-0 rank-book evidence policies.
4. Score prior outcomes whose future sessions now exist.
5. Write the prospective standards report and upload all run evidence.

Optional pause: set repository variable `ML_LIVE_SHADOW_ENABLED=0`.

## Manual commands

```bash
ML_DATABASE_URL=... python3 -m koel.ml.live_capture \
  --cycles 1 --book-limit 25 --include-daily-summary

ML_DATABASE_URL=... python3 -m koel.ml.snapshot export \
  --dataset hybrid --output /tmp/koel-live-snapshot

ML_DATABASE_URL=... python3 -m koel.ml.live_shadow \
  --snapshot /tmp/koel-live-snapshot

# Research-only point-in-time DE-persist replay (NOT E7-eligible):
# writes shadow_policy_rank_de_persist_hist_v1 / shadow_hist_persist_book
ML_DATABASE_URL=... python3 -m koel.ml.live_shadow \
  --snapshot /tmp/koel-hist-snapshot-split \
  --as-of 2026-07-22
# or: bash scripts/ml_hist_de_persist.sh --snapshot /tmp/koel-hist-snapshot-split --days 20

# Prefer shadow-first scoring so older non-shadow rows cannot starve E7/E8.
DATABASE_URL=... python3 -m koel ml-score-outcomes --model-prefix shadow --limit 20000
ML_DATABASE_URL=... python3 -m koel.ml.live_shadow_report
```

### One-shot / multi-day wrapper (preferred for E7 accumulation)

```bash
# After close (once):
bash scripts/ml_daily_shadow.sh

# Sleep until next weekday 14:40 Asia/Colombo, run once:
bash scripts/ml_daily_shadow.sh --wait

# Accumulate many trading days (wait before each day after the first unless --wait):
bash scripts/ml_daily_shadow.sh --loop 60 --wait
```

The wrapper exports the split hybrid snapshot, emits `live_shadow`, force
path-backfills recent CSE bars, scores `--model-prefix shadow`, prints
`live_shadow_report`, and logs `E7_STATUS non_partial_sessions=…/60`. Logs land
under `/tmp/koel-daily-shadow/`.

`live_shadow` refuses to emit a final model before 14:35 SLT. `--allow-partial`
exists only for explicit canaries; those model versions and gates include
`partial` and are excluded from standards.

## Self-learning identity

The workflow retrains each fixed algorithm policy after every completed session,
using the newly persisted bars and filings. It is a prequential self-learning
policy: predict the next session, score when that session matures, then include
the matured data in later training.

Every daily fit has a unique immutable `model_version` derived from:

- policy ID;
- composite bars + filings snapshot SHA;
- issue session;
- code revision;
- live pressure-input SHA when applicable.

`model_id` remains the stable policy ID. Standards aggregate across daily
instances of the same fixed policy. Changing features, hyperparameters,
eligibility, target or gate requires a new policy ID and starts a new
qualification epoch. Prediction conflicts use `DO NOTHING`; reruns cannot
rewrite prior evidence.

Current base policies:

- `shadow_policy_abs_xgb2_v1`
- `shadow_policy_abs_hgb2_v1`
- `shadow_policy_abs_xgb_domain_v1`
- `shadow_policy_abs_xgb2_p005_v1` (selective top 0.5% of abs xgb)
- `shadow_policy_abs_xgb2_pressure_v1` (book/pressure overlay)
- `shadow_policy_rank_de_persist_v1` (Loop 0 only: relative
  `double_ensemble_native` + `persistence_exit_10_top_bottom_05` book;
  emits book legs only with gates `shadow_persist_book` /
  `shadow_partial_persist_book`; offline split-adjusted reference
  +0.49% net@112bps — not user-facing)
- `shadow_policy_rank_de_h3_weekly_v1` (Loop 0 only: relative/h3
  `double_ensemble_native` + `weekly_5_sessions_top_bottom_05` book;
  emits book legs only with gates `shadow_h3_weekly_book` /
  `shadow_partial_h3_weekly_book`; rebuilds the book when
  `session_index % 5 == 0`, otherwise re-emits prior sides with incremented
  ages; offline split-adjusted reference +0.27% net@112bps — not user-facing)

The report compares policies automatically. Passing a standard only makes a
policy review-eligible; it does not write `forecast_points` or send alerts.

## Factors and naming

The base challenger uses:

- path and temporal return/volume/range lags;
- market breadth and cross-sectional context;
- source, missingness and flat-history features;
- publication-safe filing metrics.

The pressure challenger adds:

- median public displayed-book imbalance;
- imbalance sign persistence;
- imbalance slope;
- tick-rule signed incremental cumulative-volume proxy.

These are **not executed buy pressure**. The public CSE feed does not identify
aggressor side, and the overlay has no historical qualification yet.

## Promotion standard

Each frozen non-partial model version must independently reach:

- precision and one-sided 95% LCB ≥90%;
- at least 500 scored emits;
- at least 80 symbols and 60 sessions;
- maximum symbol and session share ≤5%.

Always-on/all-company accuracy is reported separately. Sparse selective
precision must never be described as accuracy for all listed companies.

No accuracy is available on issue day. H1 first becomes scorable after the next
official CSE session is persisted.

### DE-persist report columns

Loop-0 `shadow_policy_rank_de_persist_v1` rows (gates `shadow_persist_book` /
`shadow_partial_persist_book`) appear in `standards.json` with `book_policy=true`.
They report emit counts (`rows`), scored counts, direction hit-rate (`precision`
when matured), RankIC, net@112 (`post_cost_mean_return`), and concentration
(`max_symbol_share`, `max_session_share`). The selective 90% SuccessContract
(`contract_met`) is `null` for book policies; `rank_book_contract_met` is a
reserved stub for a future rank-book qualification gate — not the abs-direction
standard above.

`shadow_policy_rank_de_h3_weekly_v1` uses the same report treatment. Its
`horizon_days` is 3, and partial canaries use `shadow_partial_h3_weekly_book`;
non-partial evidence uses `shadow_h3_weekly_book`.

Research only — not financial advice.
