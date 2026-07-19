# Ceyfi Market ↔ Quiverly bridge (Phase 1)

**Host UI:** [ArdenoStudio/ceyfi](https://github.com/ArdenoStudio/ceyfi) `/market`  
**Engine:** this repo — poller, rules, `/api/v1/*`

## Ceyfi side

- Backend: `GET /api/market/{overview,watchlist,alerts,fires,fires/{id}}`
- Without `CHIME_API_BASE`: deterministic mocks per demo persona
- With `CHIME_API_BASE=https://…chime`: proxies Quiverly after `POST /api/v1/auth/demo`
- Frontend: `/market`, `/market/watchlist`, `/market/alerts`, `/market/alerts/[id]`
- Alert detail shows **cash context** from Ceyfi `financial-snapshot` + NFA; broker CTA disabled until Phase 4

Env (Ceyfi backend):

```bash
CHIME_API_BASE=http://localhost:3000   # optional
CHIME_DEMO_TELEGRAM_ID=123456789       # must be on Quiverly DASH_DEMO_TELEGRAM_IDS
```

## Quiverly side

- Existing: watchlist, alerts, `alerts/history`, symbols
- Added: `GET /api/v1/alerts/fires` → alias of history (Ceyfi naming)

## Non-goals

- No Buy button / order entry
- Ceyfi never scrapes cse.lk
- Quiverly dash is not the consumer invest host
