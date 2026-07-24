# E8 shadow scoring progress — 2026-07-24

Research only — not financial advice. **E7/E8 still open.**

## Why scored legs were stuck at 0

1. `ml-score-outcomes` default FIFO examines only 5000 oldest unscored
   `forecast_outcomes` rows; thousands of older non-shadow rows starve shadows.
2. `daily_bars` coverage after 2026-07-21 was thin (Jul-22/23 ~40 symbols) until
   a forced CSE `path-backfill --force --period 2` pass.
3. Non-partial DE-persist legs are dated **2026-07-24**; h1 realization needs the
   **next** session (2026-07-25+), which does not exist yet on a Friday close.

## Actions taken

| Action | Result |
|---|---|
| Direct shadow score pass #1 | 178 scored / 2416 skipped (pre Jul-24 bars) |
| `path-backfill --force --period 2 --limit 80` | 80 ok; `daily_bars` max → **2026-07-24** |
| Direct shadow score pass #2 | +383 scored |
| Full-universe period-2 backfill | in flight (`/tmp/path-backfill-all.log`) |

## DE-persist / h3-weekly (E7/E8 gates)

| Policy | Gate | Scored / total | Non-partial scored sessions | Notes |
|---|---|---:|---:|---|
| `shadow_policy_rank_de_persist_v1` | `shadow_persist_book` | **0 / 16** | **0** | Jul-24 emit; needs Jul-25+ bars |
| `shadow_policy_rank_de_persist_v1` | `shadow_partial_persist_book` | **6 / 38** | n/a (partial excluded) | Jul-23 partial; hit_rate ~0.60 on scored |
| `shadow_policy_rank_de_h3_weekly_v1` | `shadow_h3_weekly_book` | **0 / 16** | **0** | h3 needs 3 sessions after issue |

## E7 / E8 status

- **E7:** still **1/60** non-partial emit sessions; scored non-partial DE sessions **0**.
- **E8:** prospective precision/LCB vs offline **insufficient** (no non-partial
  scored DE legs yet).
- Next non-partial emit scheduled: **2026-07-27 14:40 Asia/Colombo**
  (`tmux koel-shadow-mon`). Re-score after that session’s next close.

## Ops note

Prefer scoring shadows explicitly (or raise/loop `ml-score-outcomes`) after each
path-backfill; do not assume a single default pass drains the shadow ledger.
