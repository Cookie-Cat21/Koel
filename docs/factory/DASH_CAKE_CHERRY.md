# Product pivot — Dash cake, Telegram cherry

**Status:** Active (2026-07-14)  
**Replaces:** “thin management UI only / Telegram-primary” framing in older DASH notes.

## One-liner

Chime is a **CSE market dashboard** you open to browse, watch, and inspect.
**Telegram push alerts** are the cherry on top — the gap Tracker Pro still
leaves open (browser-open-only alerts).

## Layers

| Layer | Role |
|---|---|
| **Cake (primary)** | Web dashboard: Overview, Browse, Watchlist, Symbol detail, Alerts CRUD, History, Health |
| **Cherry (differentiator)** | Telegram bot fires the moment a rule matches — no tab required |

## Still deferred (not Tracker Pro clone overnight)

- Portfolio quantities / cost basis / P&L / tax reports
- Full TA charting suites / order-book terminal
- Payments / native apps
- Screener with 20 filters (keep Browse denser but not a quant terminal)

## Near-realtime prices

CSE publishes no public WebSocket tape. Chime’s path is:

`cse.lk tradeSummary` → poller (`POLL_INTERVAL_SECONDS`, min 5) → Postgres →
dash `PriceRefresh` soft-reload (~15s).

That is **near-realtime during market hours**, not a broker streaming feed.
