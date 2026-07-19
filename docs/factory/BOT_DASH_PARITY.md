# Bot / Dashboard Alert Parity

Quiverly remains Telegram-first. The dashboard is a thin management surface over
the same Postgres-backed watchlist, rules, and fire history.

| Alert type | Bot command | Dashboard create | Delivery surface | Notes |
|---|---:|---:|---|---|
| Price crosses above | Yes | Yes | Telegram | Same `price_above` rule. |
| Price crosses below | Yes | Yes | Telegram | Same `price_below` rule. |
| Daily % move | Yes | Yes | Telegram | One fire per Colombo trading day. |
| Disclosure / announcement | Yes | Yes | Telegram | Dashboard supports optional category filter. |
| Volume spike | Yes | Yes | Telegram | Uses persisted `price_snapshots.volume`. |
| Heavy volume + up | Yes | Yes | Telegram | Uses volume multiple plus positive move. |
| Heavy volume + down | Yes | Yes | Telegram | Uses volume multiple plus negative move. |
| Crossing volume | Yes | Yes | Telegram | Uses `price_snapshots.crossing_volume`. |
| Big print | Yes | Yes | Telegram | Uses day-tape `big_prints`. |
| Open gap | Yes | Yes | Telegram | One fire per Colombo trading day. |
| Buy-in board | Yes | Yes | Telegram | Notice-style rule, no threshold. |
| Non-compliance | Yes | Yes | Telegram | Notice-style rule, no threshold. |
| Market halt / notice | Yes | Yes | Telegram | Uses synthetic `MARKET` symbol. |
| Bid-heavy order book | Yes | Yes | Telegram | Uses public order-book totals. |
| Ask-heavy order book | Yes | Yes | Telegram | Uses public order-book totals. |
| EPS above / below | Yes | Yes | Telegram | Financial metrics feature-flagged; dashboard metrics API exposes latest extracted rows. |
| EPS / revenue / profit YoY | Yes | Yes | Telegram | Financial metrics feature-flagged; dashboard metrics API exposes YoY comparisons. |

## Dashboard-only operations

| Operation | Purpose | Notes |
|---|---|---|
| Alert quota | Abuse guard | `users.alert_quota_max` caps active dashboard alert creates. |
| Test fire | Audit-only dry run | Inserts `[dry-run]` `alert_log` row; no Telegram send. |
| Mute | Temporary suppression | Dashboard PATCH writes `alert_rules.muted_until`; the rule engine skips future-dated mutes. |
| User preferences | Delivery settings | Dashboard settings reads/writes `digest_enabled`, `quiet_hours_start`, and `quiet_hours_end`. |

## Runtime notes

- Halt create on the dash forces symbol `MARKET` (bot parity).
- Quiet hours from Settings are honored by the poller delivery path: Telegram
  sends are held until outside the Colombo local window (no retry-counter burn).
- Digest flag is stored for a future EOD digest job.
