# Chime

Telegram-first alerting layer for the Colombo Stock Exchange (CSE).

Chime is a background watcher, not a dashboard. You set an alert condition —
a price threshold, a daily % move, or "any new disclosure for this company" —
and get a Telegram message the moment it fires, with no browser tab or app
open. Full product plan: [CLAUDE.md](CLAUDE.md). Endpoint notes:
[docs/endpoint_probe_report.md](docs/endpoint_probe_report.md).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill TELEGRAM_BOT_TOKEN + DATABASE_URL
python -m chime migrate
python -m chime both   # or: bot | poller | tick --force
```

## Local Postgres

`docker-compose.yml` runs Postgres 16 (`chime` / `chime` / db `chime` on `:5432`).

```bash
make up && make migrate
```

`make down` stops the container. `make help` lists all targets. Point `DATABASE_URL` at it (see `.env.example`).

## Commands

| Command | What it does |
|---|---|
| `python -m chime migrate` | Apply SQL migrations in `db/migrations/` |
| `python -m chime bot` | Telegram bot only |
| `python -m chime poller` | Market-hours poller + rule engine only |
| `python -m chime both` | Bot + poller in one process |
| `python -m chime tick --force` | One poll cycle (ignores market hours) |

## Latency SLO

Alert **claim → Telegram send** is instrumented (`alert_latency_ms`) and targeted
at p95 &lt; 5s. End-to-end CSE print → Telegram is bounded by
`POLL_INTERVAL_SECONDS` (default 60s, with jitter) — the honest product SLO is
“within one poll cycle during market hours,” not sub-5s from the exchange tick.

When `bot`, `poller`, or `both` is running:

`http://$HEALTH_HOST:$HEALTH_PORT/health` (defaults `127.0.0.1:8080`)

Returns JSON liveness / last-tick status (`200` ok, `503` degraded).

## Layout

```
chime/                  Python package
  adapters/             cse.lk HTTP adapter
  poller.py             market-hours polling loop
  rules.py              alert rule engine
  bot.py                Telegram bot (only user-facing surface in v1)
  storage.py            Postgres access
  config.py             env-based settings
  health.py             /health HTTP endpoint
db/migrations/          SQL migrations
docs/                   probe report, samples, resources
tests/
```

## Stack

Python · python-telegram-bot · Postgres · APScheduler · httpx

Config via environment — see `.env.example`. Never commit `.env`.
Production process list + secrets: [docs/runbooks/PRODUCTION.md](docs/runbooks/PRODUCTION.md).
Log field glossary (`alert_latency_ms`, dead letter, `watched_missing`):
[docs/ops/LOG_FIELDS.md](docs/ops/LOG_FIELDS.md).
Third-party licenses: [THIRD_PARTY.md](THIRD_PARTY.md).

## Factory / thin dashboard

Quality-gated workstreams live under [docs/factory/](docs/factory/)
([COMMIT_FACTORY.md](docs/factory/COMMIT_FACTORY.md),
[DASH_IA.md](docs/factory/DASH_IA.md)). Telegram remains the primary
user surface; a thin management dashboard (Next.js + Tailwind + shadcn)
is secondary — watchlist / alerts / fire history only, not a trading
terminal.

### Dashboard runbook (`web/`)

Local demo auth (ADR 001) — Postgres only; never calls cse.lk from `web/`.

```bash
# 1) Backend DB (same as bot/poller)
make up && make migrate
cp .env.example .env   # DATABASE_URL=postgresql://chime:chime@localhost:5432/chime

# 2) Dashboard
cd web
cp .env.example .env.local
# Required:
#   DATABASE_URL=postgresql://chime:chime@localhost:5432/chime
#   DASH_DEMO_AUTH=1
#   DASH_DEMO_TELEGRAM_IDS=123456789   # allowlist; must match a users.telegram_id
#   DASH_SESSION_SECRET=<long random>
# Optional: DASH_DEFAULT_TELEGRAM_ID=123456789  (pre-fill /login)
# Optional: HEALTH_URL=http://127.0.0.1:8080/health  (poller proxy)
npm install
npm run dev
```

Open [http://localhost:3000/login](http://localhost:3000/login). Demo sign-in
posts `{ "telegram_id": <allowlisted id> }` → HttpOnly `chime_session` + CSRF.
Mutations need matching `X-CSRF-Token`. Details: [web/README.md](web/README.md),
[docs/adr/001-dash-auth.md](docs/adr/001-dash-auth.md).

## Disclaimer

Chime relays publicly available market information. It is an information
tool, not investment advice.
