# Chime dashboard (`web/`)

Next.js App Router + Tailwind + shadcn/ui scaffold for the thin CSE alert
dashboard. Reads **Postgres only** — never calls cse.lk from this package.

## Setup

```bash
cd web
cp .env.example .env.local
# edit DASH_* and DATABASE_URL
npm install
npm run dev
```

Open [http://localhost:3000/login](http://localhost:3000/login).

### Required env (ADR 001)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres (shared with bot) |
| `DASH_DEMO_AUTH=1` | Opt-in demo login |
| `DASH_DEMO_TELEGRAM_IDS` | Comma-separated allowlist |
| `DASH_SESSION_SECRET` | Non-empty HMAC key for `chime_session` cookie |
| `DASH_DEFAULT_TELEGRAM_ID` | Optional default on `/login` (must be allowlisted) |

## Scripts

- `npm run dev` — development server
- `npm run build` / `npm start` — production
- `npm run lint` — ESLint

## Auth (v1 demo)

`POST /api/v1/auth/demo` with `{ "telegram_id": number }` mints a signed
HttpOnly `chime_session` cookie bound to `users.id`, plus CSRF material
(`chime_csrf` + `csrf_token` in JSON). Login is CSRF-exempt; all other
mutations (including `POST /api/v1/auth/logout`) require matching
`X-CSRF-Token`. See `docs/adr/001-dash-auth.md`.

## Read APIs (session required)

| Method | Path |
|---|---|
| `GET` | `/api/v1/me` |
| `GET` | `/api/v1/watchlist` |
| `GET` | `/api/v1/alerts` |
| `GET` | `/api/v1/alerts/history` |
| `GET` | `/api/v1/health` |

Shapes follow `docs/factory/API_CONTRACT_V1.md`. Data from `DATABASE_URL` only.
