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

## Commands

| Command | What it does |
|---|---|
| `python -m chime migrate` | Apply SQL migrations in `db/migrations/` |
| `python -m chime bot` | Telegram bot only |
| `python -m chime poller` | Market-hours poller + rule engine only |
| `python -m chime both` | Bot + poller in one process |
| `python -m chime tick --force` | One poll cycle (ignores market hours) |

## Health check

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
Third-party licenses: [THIRD_PARTY.md](THIRD_PARTY.md).

## Disclaimer

Chime relays publicly available market information. It is an information
tool, not investment advice.
