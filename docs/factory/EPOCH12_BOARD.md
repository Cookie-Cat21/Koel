# Epoch 12 Board — Residual reliability + thin ops polish

**Status:** OPEN

Fence-legal only. Theme: residual alert delivery reliability, health honesty,
small dashboard ops/readability polish, and focused tests/docs. No portfolio/P&L,
screener, technical analysis, payments, native app, competitor scrape, or cse.lk
calls from `web/`.

| ID | Item | Status |
|---|---|---|
| E12-C01 | Durable Telegram-OK outcome after total DB write failure/restart | OPEN |
| E12-C02 | Disclosure adapter catch-up for DOA-only publish lag vs `createdDate` | OPEN |
| E12-O01 | `both` mode pool contention signal in loopback health | OPEN |
| E12-O02 | Web health proxy degrades on `price_poll_ok=false` / `disclosure_poll_ok=false` | OPEN |
| E12-D01 | Alerts history distinguishes retrying vs dead-lettered delivery rows | OPEN |
| E12-D02 | Health page shows stale tick/snapshot age as explicit ops copy | OPEN |
| E12-Q01 | Route/page regression tests for health degradation and no web CSE calls | OPEN |
| E12-A01 | Document `alert_log` delivery-state contract for ops/debugging | OPEN |

Never farm. One concern per row.
