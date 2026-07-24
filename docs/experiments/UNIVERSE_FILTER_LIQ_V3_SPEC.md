# Universe filter LIQ v3 spec

Status: declared after W2 `liq_v2` kill (35 328 samples, −94.4%). Research only;
not financial advice.

## Why v3 exists

Nested relative/h1 with `liq_v2` still dropped **~94%** of training rows (636 455 →
35 328). RankIC collapsed (best xgb 0.2136 vs frozen 0.2861); 0 selective emits; no
cost flip. See `UNIVERSE_FILTER_LIQ_V2_NESTED_20260723.md`.

Hypothesis: ADV20 and CSE-session floors dominate sample loss on the CSE matrix.
`liq_v3` removes the ADV gate entirely and keeps only a flat-fraction dead-bar
filter plus a minimal CSE-session floor.

## Manifest

- name: `liq_v3`
- min ADV20: `0` (no volume floor — gate skipped when zero)
- max flat fraction 60: `0.40`
- min CSE sessions 60: `5`

## Application point

`cpu_exhaust` applies this when `--universe-filter liq_v3` is set. Prior presets
(`liq_v1`, `liq_v2`) remain for comparison. Default `--universe-filter ""` keeps
the frozen champion matrix.

Order: base samples → research enrich → optional feature pack → universe filter
→ relative demean → cross-section enrich.

## Point-in-time rule

Same as v1/v2: eligibility per sample uses bars with `trade_date <= as_of` only.

## Success criteria (W2 continuation)

- Post-filter samples **≥100 000** (minimum bar for nested stability).
- RankIC within **+0.005** of frozen xgb 0.2861 **or** selective emits ≥2× frozen
  **or** net@112 improvement ≥0.10 pp on persistence champion variant.

If v3 still collapses below 100 k, **retire universe-filter lever** for this
snapshot — flat-only filtering cannot recover tradeable depth on current CSE
coverage.
