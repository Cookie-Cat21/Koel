# CPU Improve 6K — 2026-07-23

6 cycles × 1000 configs (6000 total) on CPU improvement loop.

## Verdict

**No breakthrough.** Nothing beat nested `xgb_two_stage` RankIC **0.2861**; no positive net@112.

- Best test RankIC: **0.27461166442870927** (`lgb_9faa353fb4`, cycle 0)
- Best net@112: **-0.49%** (`lgb_9ff04b8c4d`, cycle 3)
- vs persistence DE +0.36%: still **-0.85pp** short

| Cycle | Theme | test_ic | net112 | pos112 |
|------:|-------|--------:|-------:|:------:|
| 0 | lgb | 0.27461166442870927 | -0.90% | False |
| 1 | xgb | 0.24481666223207904 | -0.99% | False |
| 2 | blend | 0.2608148243763402 | -0.81% | False |
| 3 | lgb | 0.26165048162573323 | -0.67% | False |
| 4 | lgb_shaped | 0.26477748509152543 | -0.70% | False |
| 5 | lgb | 0.2580494241334145 | -0.78% | False |

Full harvest: `docs/experiments/cpu_improve_6k_harvest.json`
