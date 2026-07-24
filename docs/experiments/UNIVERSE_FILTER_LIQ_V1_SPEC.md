# Universe filter LIQ v1 spec

Status: declared for W2 training experiments. Research only; not financial advice.

## Manifest

- name: `liq_v1`
- version: `v1`
- min ADV20: `1000.0` mean share volume over the last 20 visible bars
- max flat fraction 60: `0.40`, matching the existing `flat_fraction_60` concept
- min CSE sessions 60: `20` official-CSE rows in the trailing 60 visible bars

## Application point

`cpu_exhaust` applies this only when `--universe-filter liq_v1` is set. Default
`--universe-filter ""` keeps the frozen champion matrix.

Order: base samples -> research enrich -> optional feature pack -> universe
filter -> relative demean -> cross-section enrich.

## Point-in-time rule

Eligibility is computed per sample with bars where `trade_date <= as_of`.
Future volume, future source rows, and future flat-price spans must not affect
whether a row is included.
