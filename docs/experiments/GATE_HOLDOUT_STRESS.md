# Gate holdout stress — 2026-07-17

Temporal holdout: train allowlist / calibrate on first **80%** of
`issued_at` dates in `forecast_outcomes` (`wf_fin_sector_h1`), evaluate on
last **20%**. Research only — not financial advice.

## Results (reproduced in loop)

| Gate | Holdout hit | n | Notes |
|---|---:|---:|---|
| Pure conf ≥ 0.55 | ~0.737 | ~453 | denser, below 90% |
| Pure conf ≥ 0.61 | ~0.762 | ~290 | |
| Pure conf ≥ 0.75 | ~0.825 | ~63 | |
| Pure conf ≥ 0.80 | **~0.952** | **21** | B-012 KEEP (sparse) |
| Pure conf ≥ 0.84 | 1.0 | 7 | too small |
| Sym hit ≥ 0.61 × conf ≥ 0.71 | **0.90** | **60** | **B-013 KEEP** (serve `gated_p90`) |
| In-sample-only sym≥0.71×conf≥0.61 | looked ~90% in-sample | — | **failed holdout (~82%)** — discarded |

## Serve mapping

- `gated` — calibrated thr (~0.45–0.55) denser selective path (~73% full-sample)
- `gated_p90` — allowlist from `reliable_symbols.json` + conf thr (defaults **0.61 / 0.71**)

## Shuffle audit (B-010)

Label-shuffle walk-forward mean hit ≈ **0.524** across 8 folds — PASS (no
gross leakage).

Re-run: rebuild outcomes with `ml-backfill-outcomes`, then sweep scripts in
Loop C / agent notes.
