# Epoch 12 Board — Residual reliability + thin ops polish

**Status:** CLEAR

Fence-legal only. Theme: residual alert delivery reliability, health honesty,
small dashboard ops/readability polish, and focused tests/docs. No portfolio/P&L,
screener, technical analysis, payments, native app, competitor scrape, or cse.lk
calls from `web/`.

| ID | Item | Status |
|---|---|---|
| E12-C01 | Durable Telegram-OK outcome after total DB write failure/restart | DONE |
| E12-C02 | Disclosure adapter catch-up for DOA-only publish lag vs `createdDate` | DONE |
| E12-O01 | `both` mode pool contention signal in loopback health | DONE |
| E12-O02 | Web health proxy degrades on `price_poll_ok=false` / `disclosure_poll_ok=false` | DONE |
| E12-D01 | Alerts history distinguishes retrying vs dead-lettered delivery rows | DONE |
| E12-D02 | Health page shows stale tick/snapshot age as explicit ops copy | DONE |
| E12-Q01 | Route/page regression tests for health degradation and no web CSE calls | DONE |
| E12-A01 | Document `alert_log` delivery-state contract for ops/debugging | DONE |

Never farm. One concern per row.
