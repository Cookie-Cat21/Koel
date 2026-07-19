# koel

Tijori-for-CSE: thin **Browse**, AI **filing briefs**, and real **Telegram push**
for the Colombo Stock Exchange — not a portfolio tracker or trading terminal.

koel is a background watcher. You set an alert condition — a price threshold,
a daily % move, or "any new disclosure for this company" — and get a Telegram
message the moment it fires, with no browser tab or app open. The thin dash
adds `/market` Browse and optional plain-language filing briefs on disclosures;
push stays primary. Full product plan: [CLAUDE.md](CLAUDE.md). Tijori plan:
[docs/factory/TIJORI_CSE_PLAN.md](docs/factory/TIJORI_CSE_PLAN.md). Endpoint notes:
[docs/endpoint_probe_report.md](docs/endpoint_probe_report.md).


## Rebrand note

The **product name** is **koel** (wordmark: lowercase `koel`; mark: capital **K**).
The internal Python package, CLI (`python -m chime`), Postgres role/database name,
env vars, and this repository’s historical codename remain **`chime`** for now —
only user-facing product surfaces were renamed in the koel rebrand.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# Optional: PDF text extract for AI filing briefs (pypdf) — needed when
# AI_BRIEFS_ENABLED=1 and the poller drains disclosure_briefs:
#   pip install -e ".[briefs]"
#   # or combined: pip install -e ".[dev,briefs]"
cp .env.example .env   # fill TELEGRAM_BOT_TOKEN + DATABASE_URL
python -m chime migrate
python -m chime both   # or: bot | poller | tick --force
```

## Local Postgres

`docker-compose.yml` runs Postgres 16 (`chime` / `chime` / db `chime` on `:5432`).
Optional profile **`web`** builds the Next.js dash (`make up-web` → `:3000`).

```bash
make up && make migrate
# optional dash:
make up-web
```

`make down` / `make down-web` stop the stack. `make help` lists all targets.
Point `DATABASE_URL` at it (see `.env.example`).

## Commands

| Command | What it does |
|---|---|
| `python -m chime migrate` | Apply SQL migrations in `db/migrations/` |
| `python -m chime bot` | Telegram bot only |
| `python -m chime poller` | Market-hours poller + rule engine only |
| `python -m chime both` | Bot + poller in one process |
| `python -m chime tick --force` | One poll cycle (ignores market hours); seeds `/market` browse |
| `make tick` | Same as `python -m chime tick --force` |

Bot and `both` start Telegram long-polling with `drop_pending_updates=True`, so
queued messages from downtime are discarded on restart (avoids replaying stale
`/watch` / `/alert` commands after a deploy).

### Bot commands (Telegram)

| Command | What it does |
|---|---|
| `/start` | Register user, short explainer + NFA |
| `/help` | List commands + disclosure/alert notes + NFA |
| `/watch SYMBOL` | Add symbol to watchlist |
| `/unwatch SYMBOL` | Remove symbol; deactivates that user’s rules for it |
| `/alert SYMBOL above PRICE` | Fire when last price crosses above threshold |
| `/alert SYMBOL below PRICE` | Fire when last price crosses below threshold |
| `/alert SYMBOL move PERCENT` | Fire when daily % move exceeds threshold |
| `/alert SYMBOL disclosure [CATEGORY]` | Fire on new filing (optional title substring) |
| `/alert SYMBOL volume N` | Unusual volume (≥ N× recent daily average) |
| `/alert SYMBOL volup N` / `voldown N` | Heavy volume while price up / down |
| `/alert SYMBOL crossing N` | Crossing volume ≥ N× recent average |
| `/alert SYMBOL print QTY` | Single day-tape print ≥ QTY shares |
| `/alert SYMBOL gap PERCENT` | Open gap vs previous close |
| `/alert SYMBOL buyin` / `noncompliance` | Buy-in board / non-compliance notice |
| `/alert MARKET halt` | Market-wide halt / system notice |
| `/alert SYMBOL bidheavy N` / `askheavy N` | Order-book bid/ask size imbalance (≥ N×) |
| `/cancel ALERT_ID` | Soft-cancel an active rule |
| `/myalerts` | List active alerts only (cancelled omitted) |
| `/mywatchlist` | List watched symbols |
| `/brief SYMBOL` | Read-only latest ready AI filing brief (DB only; no LLM call). Empty → “AI briefs are off” or “none yet” |


## Latency SLO

Alert **claim → Telegram send** is instrumented (`alert_latency_ms`) and targeted
at p95 &lt; 5s. End-to-end CSE print → Telegram is bounded by
`POLL_INTERVAL_SECONDS` (default 15s, with jitter) — the honest product SLO is
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
[DASH_IA.md](docs/factory/DASH_IA.md),
[TIJORI_CSE_PLAN.md](docs/factory/TIJORI_CSE_PLAN.md),
wave rollup [TIJORI_WAVE_REPORT.md](docs/factory/passes/TIJORI_WAVE_REPORT.md)).
Telegram remains the primary user surface; a thin management + browse dashboard
(Next.js + Tailwind + shadcn) is secondary — watchlist / alerts / fire history /
symbol browse only, not a trading terminal.

### Dashboard runbook (`web/`)

Local demo auth (ADR 001) — Postgres only; never calls cse.lk from `web/`.

```bash
# 1) Backend DB (same as bot/poller)
make up && make migrate
cp .env.example .env   # DATABASE_URL=postgresql://chime:chime@localhost:5432/chime

# 2) Seed /market browse (one forced CSE poll → stocks + price_snapshots)
make tick   # or: python -m chime tick --force

# 3) Dashboard
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

Empty `/market` ⇒ no snapshots yet — run `make tick` (or leave `poller`/`both`
running). Open [http://localhost:3000/login](http://localhost:3000/login). Demo
sign-in posts `{ "telegram_id": <allowlisted id> }` → HttpOnly `chime_session` +
CSRF. Mutations need matching `X-CSRF-Token`. Details:
[web/README.md](web/README.md), [docs/adr/001-dash-auth.md](docs/adr/001-dash-auth.md),
[docs/runbooks/TIJORI.md](docs/runbooks/TIJORI.md).

## Disclaimer

koel relays publicly available market information. It is an information
tool, not investment advice.
