# Universe filter LIQ v2 spec

Status: declared after W2 `liq_v1` kill. Research only; not financial advice.

## Why v2 exists

Nested relative/h1 with `liq_v1` dropped **~93%** of training rows (502 535 →
32 535). RankIC collapsed (best DE 0.18 vs frozen 0.25); xgb/hgb failed on the
shrunk matrix. See `UNIVERSE_FILTER_LIQ_V1_NESTED_20260723.md`.

`liq_v2` relaxes thresholds to keep a larger liquid, tradeable universe while
still excluding penny-volume and dead-flat names.

## Manifest

- name: `liq_v2`
- version: `v2`
- min ADV20: `100.0` (was `1000.0` in v1)
- max flat fraction 60: `0.50` (was `0.40`)
- min CSE sessions 60: `10` (was `20`)

## Application point

`cpu_exhaust` applies this when `--universe-filter liq_v2` is set. `liq_v1`
remains available unchanged for comparison. Default `--universe-filter ""` keeps
the frozen champion matrix.

Order: base samples → research enrich → optional feature pack → universe filter
→ relative demean → cross-section enrich.

## Point-in-time rule

Same as v1: eligibility per sample uses bars with `trade_date <= as_of` only.
