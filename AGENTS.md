# AGENTS.md

Chime — Telegram-first alerting layer for the Colombo Stock Exchange (CSE).
Product plan and non-goals live in `CLAUDE.md`; developer commands in `README.md`.

## Cursor Cloud specific instructions

The startup update script installs dependencies only (Python `pip install -e ".[dev]"`
and `web/` `npm ci`). Everything below is not run automatically — future agents must
start the datastore/services themselves.

### Services

| Service | Language / runtime | Run (dev) | Notes |
|---|---|---|---|
| Postgres 16 | apt package (not Docker here) | `sudo pg_ctlcluster 16 main start` | Shared DB for backend + dashboard. |
| Backend (`chime`) | Python 3.12 | `python3 -m chime {bot,poller,both,tick}` | `bot`/`poller`/`both`/`tick` require `TELEGRAM_BOT_TOKEN`; `migrate` does not. |
| Dashboard (`web/`) | Node 22 / Next.js 16 | `cd web && npm run dev` (`:3000`) | Postgres-only; never calls cse.lk. |

### Postgres (no Docker in this VM)

`docker` is not installed here, so the `docker-compose.yml` / `make up` path does **not**
work. Postgres 16 is installed as an apt package instead. It is not started by the update
script — start it each session and (re)create the role/db if missing:

```bash
sudo pg_ctlcluster 16 main start
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='chime'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE chime LOGIN PASSWORD 'chime';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='chime'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE DATABASE chime OWNER chime;"
```

`DATABASE_URL=postgresql://chime:chime@localhost:5432/chime` (the repo default). Copy
`.env.example` → `.env` for the backend; the `.env` default `DATABASE_URL` already matches.
Apply migrations with `python3 -m chime.migrate` (idempotent).

> **Injected `DATABASE_URL` secret overrides local Postgres.** This VM ships with
> Cloud Agent secrets in the OS env (`env | grep DASH_`), including a **Neon**
> `DATABASE_URL` (`…neon.tech/neondb`) plus a real `DASH_SESSION_SECRET`,
> `DASH_DEMO_TELEGRAM_IDS`, `DASH_DEFAULT_TELEGRAM_ID`, and `TELEGRAM_BOT_TOKEN`.
> That injected Neon DB is already migrated + richly seeded, and both the backend
> (`python3 -m chime …` without an explicit `DATABASE_URL`) and the dashboard
> (Next.js does **not** let `.env.local` override an existing `process.env` var)
> will talk to Neon, **not** the local cluster above. So: the local-Postgres setup
> is optional; to force local instead, pass `DATABASE_URL=…localhost…` inline on
> the backend command. For the dashboard, just sign in with an ID from the injected
> `DASH_DEMO_TELEGRAM_IDS` allowlist (e.g. `9001001`) — `ensureUser` creates the
> row on first login. Never run integration `pytest` with the injected Neon URL
> exported (it writes fixtures into that shared DB).

### Non-obvious gotchas

- Use `python3`, not `python` — the CLI examples in `README.md`/`Makefile` say `python`, but
  only `python3` exists on this VM.
- pip installs need `--break-system-packages` (system Python is externally managed); scripts
  land in `~/.local/bin`, which is not on `PATH` by default (invoke tools by module, e.g.
  `python3 -m chime ...`, or add that dir to `PATH`).
- Running `pytest` with `DATABASE_URL` set writes fixture rows into that database; it does not
  fully clean up. Point tests at a throwaway DB, or `TRUNCATE ... RESTART IDENTITY CASCADE`
  before demos so the DB is pristine.
- `tick`/`bot`/`poller`/`both` require `TELEGRAM_BOT_TOKEN` even to start. For a poll-only
  smoke that never sends Telegram (no matching alert rules), a placeholder token works:
  `TELEGRAM_BOT_TOKEN=000:placeholder python3 -m chime tick --force`.
- The poller only persists `price_snapshots` for symbols that are on someone's watchlist.
  Poll a symbol you actually want by adding it to `watchlist_items` first.
- The dashboard's add-symbol input rejects symbols missing from the `stocks` table
  ("Unknown symbol"). The poller populates `stocks`; when running the dash alone, seed the
  row first (`INSERT INTO stocks (symbol) VALUES ('X.N0000') ON CONFLICT DO NOTHING;`).
- Dashboard demo auth (`web/.env.local`): needs `DASH_DEMO_AUTH=1`,
 `DASH_DEMO_TELEGRAM_IDS=<id>` matching a `users.telegram_id`, and a non-empty
 `DASH_SESSION_SECRET` (empty → session/mutate routes return 503). Mutations require the
 `X-CSRF-Token` header returned at login.
- This VM injects `DASH_DEMO_AUTH=0` and an empty `DASH_SESSION_SECRET` as real shell
 env vars into every process. Next.js gives real `process.env` precedence over `.env.local`,
 so those injected values **shadow** `web/.env.local` and demo login fails with
 `demo_auth_disabled` (403). Start the dash with the values inline instead, e.g.
 `DASH_DEMO_AUTH=1 DASH_SESSION_SECRET=$(openssl rand -hex 32) DASH_DEMO_TELEGRAM_IDS=123456789 npm run dev`.
 A `users` row with that `telegram_id` must exist (`INSERT INTO users (telegram_id) VALUES (123456789) ON CONFLICT DO NOTHING;`).
- Cloud Agent port previews use a `*.agent.cvm.dev` Host (not localhost). Next 16
  blocks `/_next/*` for unknown dev origins — `web/next.config.ts` sets
  `allowedDevOrigins` for those hosts so login JS can hydrate. Restart `npm run
  dev` after changing that list.
- Market-hours gating (09:30–14:30 `Asia/Colombo`, weekdays): the poller idles outside those
  hours — use `tick --force` to poll on demand.
