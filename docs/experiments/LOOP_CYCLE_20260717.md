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

## Next

- B-006 rolling 120d window
- B-007 filing×range interaction
- B-001/B-002 data acquisition (anti-plateau if more no-keeps)
- Stress: wait for next CSE session to score live gated emits
