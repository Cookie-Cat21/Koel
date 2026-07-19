# Market module (Quiverly-powered)

Ceyfi hosts the **Market** UI. Quiverly remains the CSE poller / alert engine.

## Routes

| Path | Purpose |
|---|---|
| `/market` | Watchlist summary + recent fires + cash context |
| `/market/watchlist` | Full watch list |
| `/market/alerts` | Active rules + fire history |
| `/market/alerts/[id]` | Fire detail + wallet liquid estimate + broker CTA (disabled) |

## Backend

`GET /api/market/*` — authenticated with Ceyfi demo Bearer token.

- Default: mock CSE payloads per persona (demo works offline)
- Optional: set `CHIME_API_BASE` to proxy live Quiverly `/api/v1/*` after demo login

```bash
# backend .env
CHIME_API_BASE=http://localhost:3000
CHIME_DEMO_TELEGRAM_ID=123456789
```

Quiverly must have `DASH_DEMO_AUTH=1`, a non-empty `DASH_SESSION_SECRET`, and
`DASH_DEMO_TELEGRAM_IDS` including that id.

## Compliance

Every Market surface carries NFA copy. **No Buy / Sell.** Broker handoff is
Phase 4 (licensed partner).
