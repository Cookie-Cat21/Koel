# koel dashboard (`web/`)

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

## CSRF (dash mutations)

Double-submit cookie: login (and optional `GET /me` refresh) sets
non-HttpOnly `chime_csrf`. Every other mutating `/api/v1/*` call must send
the same value as `X-CSRF-Token` (UI uses `apiMutate` in
`src/lib/api/client-fetch.ts`). Session is validated **before** CSRF —
no/invalid session → `401 unauthorized` even if CSRF is also wrong; never
`400 csrf_failed` without a valid session. Header≠cookie (or missing
header) with a valid session → `400 csrf_failed`. Curl contract:
`scripts/factory/test_csrf_contract.md`.

## APIs (session required)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/me` | |
| `GET` | `/api/v1/watchlist` | |
| `POST` | `/api/v1/watchlist` | CSRF; known `stocks` only; `created` soft flag (200 if already watched) |
| `DELETE` | `/api/v1/watchlist/{symbol}` | CSRF; deactivates rules |
| `GET` | `/api/v1/alerts` | |
| `POST` | `/api/v1/alerts` | CSRF; auto-watch; idempotent |
| `DELETE` | `/api/v1/alerts/{id}` | CSRF; soft cancel |
| `GET` | `/api/v1/alerts/history` | |
| `GET` | `/api/v1/symbols/{symbol}` | Slim last snapshot |
| `GET` | `/api/v1/symbols/{symbol}/snapshots` | Ascending sparkline |
| `GET` | `/api/v1/symbols/{symbol}/disclosures` | |
| `GET` | `/api/v1/health` | |

UI: `/watchlist`, `/alerts`, `/alerts/history`, `/symbols/[symbol]`, `/health`.
Shapes follow `docs/factory/API_CONTRACT_V1.md`. Data from `DATABASE_URL` only.

## Security headers

`next.config.ts` sets baseline headers on all routes: `X-Frame-Options`,
`X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, and
disables `X-Powered-By`. Strict CSP is deferred until a nonce/proxy path
exists (see Next.js CSP guide).
