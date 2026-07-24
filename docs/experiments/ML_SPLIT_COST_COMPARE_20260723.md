# Split-adjusted vs unadjusted cost-engineering comparison

- Generated: 2026-07-23T05:01:52.708882+00:00
- Unadjusted input: `/tmp/cpu-exhaust-rel-h1/nested`
- Split-adjusted input: `/tmp/cpu-exhaust-rel-h1-split/nested`
- Cost assumption: 112 bps one-way on traded notional
- Focus variant: `double_ensemble_native` / `persistence_exit_10_top_bottom_05`

## Policy gate

**Promote new shadow policy ID only if +net@112 survives on split-adjusted bars.** This run never writes `forecast_points` or live policies.

- Unadjusted DE persist net@112: **0.36%** (reference Loop 1 headline +0.36%)
- Split-adjusted DE persist net@112: **0.49%**
- Gate status: **PASS — positive net survives**

## Headline models (`persistence_exit_10_top_bottom_05`)

| Model | Unadj net@112 | Split net@112 | Δ net | Unadj RankIC | Split RankIC |
|---|---:|---:|---:|---:|---:|
| `xgb_two_stage` | 0.01% | 0.05% | 0.04% | 0.28612534061984274 | 0.28370127277126106 |
| `double_ensemble_native` | 0.36% | 0.49% | 0.13% | 0.2566437510536177 | 0.25541153289602697 |
| `hgb_two_stage` | 0.03% | -0.13% | -0.15% | 0.28162883327742366 | 0.28086965053467094 |

## Best net variant per run

- Unadjusted best: `double_ensemble_native` / `persistence_exit_10_top_bottom_05` net 0.36%
- Split-adjusted best: `double_ensemble_native` / `persistence_exit_10_top_bottom_05` net 0.49%

## Absolute champion (reference only)

Absolute `hgb_bagged` nested shards land under `/tmp/cpu-exhaust-abs-h1-split/nested/`; cost engineering was not re-run for absolute in this pass (relative DE persist gate is the promotion criterion).

## Artifacts

- Unadjusted cost JSON: `/tmp/cpu-cost-eng/cost_engineering_results.json`
- Split-adjusted cost JSON: `/tmp/cpu-cost-eng-split/cost_engineering_results.json`
- Relative nested split: `/tmp/cpu-exhaust-rel-h1-split/nested/`
- Absolute nested split: `/tmp/cpu-exhaust-abs-h1-split/nested/`
