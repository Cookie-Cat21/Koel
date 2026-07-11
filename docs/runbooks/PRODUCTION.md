# Production runbook — bot + poller + web

How to run Chime’s three surfaces in production (or a staging VM). Compose
provides Postgres by default; optional **`web` profile** builds/runs the Next.js
dash next to it (`docker compose --profile web up -d` / `make up-web`). Prefer
one poller leader per database.

## Process list (canonical)

| Process | Command | Role |
|---|---|---|
| Postgres | `docker compose up -d` (or managed DSN) | Shared DB for bot, poller, dash |
| Migrate | `python -m chime migrate` | Apply `db/migrations/` once per deploy |
| Bot + poller | `python -m chime both` | Telegram UX + market-hours poll / rules / delivery |
| *or* split | `python -m chime bot` **and** `python -m chime poller` | Same surfaces; one poller only |
| Dashboard | `cd web && npm run build && npm run start` | Thin watchlist / alerts UI (port 3000) |

Do **not** run two pollers against the same `DATABASE_URL` expecting dual
throughput — advisory lock means the second skips ticks (`lock_held_skip`).

### Recommended production layout

```text
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Postgres   │◄────│  chime both      │     │  web start  │
│  (compose / │     │  HEALTH :8080    │◄────│  :3000      │
│   managed)  │◄────│                  │     │  (Postgres  │
└─────────────┘     └──────────────────┘     │   + optional│
                                             │   HEALTH_URL)│
                                             └─────────────┘
```

1. **Secrets** — copy `.env.example` → `.env` (repo root) and `web/.env.example`
   → `web/.env.local`. Never commit either. See secret checklist below.
2. **DB** — `make up` (local) or set `DATABASE_URL` to the managed instance.
3. **Migrate** — `python -m chime migrate` (or `make migrate` with local compose).
4. **Core** — start `python -m chime both` under your process supervisor
   (systemd, Docker `CMD`, etc.). Health: `http://127.0.0.1:8080/health`
   (bind `HEALTH_HOST`/`HEALTH_PORT`; non-loopback returns liveness only).
5. **Dash** — `cd web && npm ci && npm run build && npm run start`.
   Point `DATABASE_URL` at the same DB. Set `HEALTH_URL` to the poller health
   URL if you want `/api/v1/health` to proxy tick detail.

### Supervisor sketch (systemd unit ideas)

| Unit | `ExecStart` | Restart |
|---|---|---|
| `chime-core` | `/path/.venv/bin/python -m chime both` | always |
| `chime-web` | `/usr/bin/npm run start` (`WorkingDirectory=…/web`) | always |

Environment: `EnvironmentFile=/etc/chime/chime.env` (core) and
`EnvironmentFile=/etc/chime/web.env` (dash). Keep Telegram token and session
secrets out of unit files in git.

## Compose (current)

```bash
docker compose up -d                    # Postgres 16 only
docker compose --profile web up -d --build   # Postgres + dash (:3000)
# or: make up-web
make migrate                            # waits for health when possible
```

`DATABASE_URL=postgresql://chime:chime@localhost:5432/chime` matches compose
defaults — **dev only**. Production must use a strong password / managed DSN
and must not expose Postgres on `0.0.0.0` without network controls.

Compose **`web`** service (profile `web`) builds `web/Dockerfile` (Next
standalone). Pass `DASH_SESSION_SECRET` (and demo allowlist only for lab).
`HEALTH_URL` is optional — point at the host poller health if you want the dash
to proxy tick detail.

## Health checks

| Probe | Expect |
|---|---|
| `GET http://$HEALTH_HOST:$HEALTH_PORT/health` (loopback) | `200` + JSON; `503` when DB or last tick degraded |
| Loopback field `watched_missing` | `[]` when all watched symbols appear in trade summary; non-empty list → **503** + price gaps (see [LOG_FIELDS.md](../ops/LOG_FIELDS.md)) |
| Loopback field `circuits` | Per-endpoint breaker snapshots (`state`, `failures`, …) |
| `GET /api/v1/health` (dash, session-gated) | DB ok; optional poller proxy via `HEALTH_URL` |

## Secret checklist

| Variable | Required by | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | bot / both | From @BotFather; never log |
| `DATABASE_URL` | bot, poller, web | Shared; no password in logs |
| `DASH_SESSION_SECRET` | web | Non-empty; fail-closed if empty |
| `DASH_DEMO_AUTH` | web | Must be `0` / unset on public URLs |
| `DASH_DEMO_TELEGRAM_IDS` | web (demo only) | Allowlist; never enable demo on open network |
| `DASH_DEFAULT_TELEGRAM_ID` | web (optional) | Must be in allowlist if set |
| `HEALTH_URL` | web (optional) | Poller `/health` for dash proxy |

Full templates: [`.env.example`](../../.env.example), [`web/.env.example`](../../web/.env.example).

## Ops signals (logs)

Structured JSON logs (structlog). Grep keys documented in
[docs/ops/LOG_FIELDS.md](../ops/LOG_FIELDS.md):

- `alert_latency_ms` — claim→Telegram send latency (ms)
- `alert_dead_lettered` / `dead_letter_*` — delivery exhausted
- `watched_symbols_missing` + health `watched_missing` — trade-summary gaps
- `cse_circuit_open` + health `circuits` — per-endpoint breaker state

## Latency honesty

Instrumented segment is **claim → Telegram send** (`alert_latency_ms`), target
p95 &lt; 5s under normal Telegram. CSE print → user message is bounded by
`POLL_INTERVAL_SECONDS` (default 60s + jitter), not sub-5s end-to-end.

## Disclaimer

Chime relays public market information. Not financial advice.
