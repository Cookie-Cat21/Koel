# ML cost engineering loop 1 - turnover variants

Offline evaluation only. No live policies were registered.

- Input shards: `/tmp/cpu-exhaust-rel-h1/nested/*.predictions.jsonl.gz`
- Partition: `test`
- Cost: 112 bps on traded notional
- Output artifacts: `/tmp/cpu-cost-eng/cost_engineering_results.{json,md}`
- Scores are unchanged; RankIC is repeated only to show portfolio construction did
  not alter the score stream.

## Headline

The best variant is `double_ensemble_native` with
`persistence_exit_10_top_bottom_05`: gross 3.74%, net@112bps 0.36%,
one-way turnover 1.508, 117 sessions.

This flips the saved `double_ensemble_native` baseline from -0.44% to +0.36%
mean net. The same construction also flips `xgb_two_stage` and
`hgb_two_stage` slightly positive.

## Compact model table

| Model | Daily 10% baseline net | Best variant | RankIC | Gross | Net@112bps | Turnover | Sessions |
|---|---:|---|---:|---:|---:|---:|---:|
| `xgb_two_stage` | -0.78% | `persistence_exit_10_top_bottom_05` | 0.2861 | 3.52% | 0.01% | 1.571 | 117 |
| `double_ensemble_native` | -0.44% | `persistence_exit_10_top_bottom_05` | 0.2566 | 3.74% | 0.36% | 1.508 | 117 |
| `hgb_two_stage` | -0.88% | `persistence_exit_10_top_bottom_05` | 0.2816 | 3.56% | 0.03% | 1.576 | 117 |

## Notes

- Weekly rebalance variants cut turnover sharply but gave up too much gross spread.
- Minimum holding periods helped cost but also reduced gross; `double_ensemble_native`
  min-hold-3 was barely positive at +0.01%.
- Delayed one-session rebalance was negative for these h1 shards.
