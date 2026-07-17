# Loop cycle — 2026-07-17

Research / self-improving loop notes. Not financial advice.

## Loop A (nightly)

- Backfilled **17,541** scored WF outcomes (`wf_fin_sector_h1`, 8 folds).
- Live scoreboard: hit_20d≈0.617, hit_60d≈0.601, gated_hit_20d≈0.722 (n≈8348).
- Gate calibration written to `data/ml_artifacts/gate_calibration.json`.
- Live forecast_points → outcomes emit fixed (use `MAX(as_of)`, not wall-clock today).

## Loop B (retrain)

- Always-on fin+sector challenger: **no promote** (0.5954 == champion always-on).
- **Promoted** `challenger_gated_c55_20260717` on gated metric **0.7268** vs prior gated 0.6794.

## Loop C (research)

| id | result |
|---|---|
| B-003 denser YoY | DEAD — +0.002 vs baseline, below keep bar |
| B-004 regime×conf | KEEP-PARTIAL — up_low @0.6 → 0.769 |
| B-005 conf gate | **KEEP** — thr=0.55 → 0.727 @ 11% cov; serve mode `gated` (73 emits / 292 pts) |
| B-010 shuffle | **PASS** — mean_hit=0.524 |

## Later same day

| id | result |
|---|---|
| B-006 roll120 | DEAD (+0.001) |
| B-007 interactions | DEAD (+0.001) |
| B-008 vol-scaled label | DEAD (mean −0.005) |
| B-002 market summary | BLOCKED — API returns ~2 sessions only; nightly accrual started (B-011) |
| B-012 gated_p90 | **KEEP** thr=0.84 → 90.5% @ n=42; serve `--mode gated_p90` (1 emit today) |
| B-013 reliability×conf | **KEEP** holdout-validated: sym≥0.61 & conf≥0.71 → **90%@n=60**; live serve 5 emits |

## Stress

- Temporal holdout (last 20% dates): pure conf≥0.80 → 95%@n=21; B-013 params above hold 90%@n=60.
- In-sample-only sym≥0.71&conf≥0.61 looked good but failed holdout (82%) — discarded.

## Next

- Accrue B-011 market summary + B-001 order-book history (empty outside hours)
- Score live gated/p90 emits after next CSE session
- Re-test B-002 at ≥60 market_daily_summary days
