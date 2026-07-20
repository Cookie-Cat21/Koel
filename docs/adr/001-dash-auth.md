# ADR 001 — Dashboard authentication (v1)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-11 |
| **Workstream** | WS-023 |
| **Supersedes** | WAVE1_DASH “Bearer `DASH_API_SECRET` + client `telegram_id` / `X-Telegram-Id`” sketch |
| **Related** | [API_CONTRACT_V1.md](../factory/API_CONTRACT_V1.md), [DASH_IA.md](../factory/DASH_IA.md), [R1_DASH.md](../factory/review/R1_DASH.md) |

## Context

The thin dashboard (`web/`) manages watchlists and alert rules for the same `users` rows the Telegram bot uses. WAVE1_DASH proposed a shared operator secret plus a client-supplied `telegram_id` on every request. That is universal impersonation: anyone with the secret can act as any user. R1_DASH and COMMIT_FACTORY reject that as “auth.”

Identity for Quiverly is a Telegram user. Production login should prove Telegram identity. Until the Login Widget is wired, v1 needs a **demo** path that still binds a server session to a fixed user — not per-request spoofable headers.

## Decision

### Canonical model

1. **Authenticate once** (login), then issue a **server-side session** bound to internal `users.id`.
2. **All subsequent API calls** derive `user_id` from that session — never from a client-supplied `telegram_id` header/query alone.
3. **Mutating routes** require CSRF protection (see below).
4. **Dashboard data path** is Postgres (and poller health proxy) only — **no cse.lk** calls from `web/`.

### Banned (do not implement)

| Pattern | Why |
|---|---|
| Shared secret + client-supplied `telegram_id` / `X-Telegram-Id` as sole auth | Impersonation of any user |
| Putting `DASH_API_SECRET` (or any long-lived ops secret) in the session cookie | XSS/CSRF blast radius = ops credential |
| Storing the session token in `localStorage` | XSS theft |
| Open-to-network demo auth without an allowlist | Account spam / cross-user confusion |
| Accepting forged Telegram Login Widget `hash` values in a stub | Fake “verified” identity |
| Browser → cse.lk (or any second CSE client) from the dashboard | Fence / compliance |

### v1 demo login

Enabled only when **all** of the following hold at process boot:

| Env | Role |
|---|---|
| `DASH_DEMO_AUTH=1` | Explicit opt-in; default off / refuse demo routes if unset |
| `DASH_DEMO_TELEGRAM_IDS` | Comma-separated allowlist of integer Telegram IDs |
| `DASH_SESSION_SECRET` | Non-empty signing/encryption key for the session cookie; **fail closed** if empty when any dash API is enabled |

Flow:

1. `POST /api/v1/auth/demo` with body `{ "telegram_id": number }`.
2. Server rejects unless `telegram_id` ∈ `DASH_DEMO_TELEGRAM_IDS`.
3. Resolve `users` row for that `telegram_id`. Demo may `ensure_user` **only** for allowlisted IDs (never for arbitrary clients).
4. Mint a **new** session (rotate on every successful login — no fixation).
5. Set a signed **HttpOnly** cookie (name e.g. `koel_session`) with attributes: `Secure` (HTTPS), `SameSite=Lax` (or `Strict` if same-site only), `Path=/`, short TTL (e.g. 12h) renewable on activity if desired.
6. Cookie payload is an opaque session id **or** a signed token containing `user_id` (+ expiry, version). It must **not** contain ops secrets or a raw `telegram_id` used as the sole trust anchor without signature.
7. Response body may include `{ "user": { "id", "telegram_id" } }` for UI — **not** a bearer secret for subsequent calls. Prefer cookie-only credentials.

`/login` UI: pick/enter an allowlisted demo Telegram ID (or single default from `DASH_DEFAULT_TELEGRAM_ID` if set **and** allowlisted). No “paste operator secret” story as identity.

### Future: Telegram Login Widget

| Step | Behavior |
|---|---|
| UI | Enable [Telegram Login Widget](https://core.telegram.org/widgets/login) when `DASH_TELEGRAM_LOGIN=1` and bot domain allowlist is configured |
| Verify | Server checks `hash` with bot token; reject on failure |
| Upsert | `ensure_user(telegram_id)` after successful verify |
| Session | Same cookie/session shape as demo; **drop demo endpoint in production** |

Until then: widget is a **disabled stub** — must not call verify endpoints or accept `hash` params.

### CSRF (canonical bootstrap)

Cookie sessions are automatically attached by the browser. CSRF is frozen as follows (API contract mirrors this; do not re-invent):

1. **Login** (`POST /auth/demo`, later `/auth/telegram`) is the only mutating route **exempt** from CSRF. On success it sets the HttpOnly session cookie **and** issues CSRF material: a non-HttpOnly CSRF cookie (double-submit) **and/or** `csrf_token` in the JSON body for the client to send as a header.
2. **All other mutating methods** (`POST`, `PATCH`, `PUT`, `DELETE`) under `/api/v1/*` — **including `POST /auth/logout`** — **must** require a matching `X-CSRF-Token` header (value equals the CSRF cookie / issued token). No logout exemption.
3. Reject cross-origin requests by default (deny-by-default CORS; same-origin dashboard only in v1). `SameSite` alone is not sufficient — CSRF check is mandatory on writes.
4. Optional refresh: `GET /api/v1/me` (or `GET /api/v1/auth/csrf`) may re-issue CSRF material; login remains the primary bootstrap.

### Health / ops gating

Full poller detail (`last_error`, symbol counts, tick flags) must **not** be anonymously public by default.

- `GET /api/v1/health` is **ops-gated**: requires a valid dashboard session **or** a separate ops credential documented in the API contract (not the user-impersonation anti-pattern).
- Optional public liveness subset (`status` + `db_ok` only) may be exposed later behind an explicit env flag; default is gated.

### Scope & tenancy

- Dashboard identity = one Telegram `users` row.
- No email/password, OAuth providers, or multi-tenant orgs in v1.
- Demo auth is a **single-operator / staging** tool. Multi-user production deploy requires Telegram Login (or equivalent proof) before opening the network.

## Consequences

- WAVE1_DASH Bearer + `X-Telegram-Id` tables are **obsolete**; implementers follow this ADR + [API_CONTRACT_V1.md](../factory/API_CONTRACT_V1.md).
- Pass 1 can ship read APIs behind the demo session without inventing a second identity system.
- CSRF + HttpOnly session land before mutating watchlist/alert routes (Pass 2+).
- Env keys for implementers (document in `.env.example` when `web/` scaffolds): `DASH_DEMO_AUTH`, `DASH_DEMO_TELEGRAM_IDS`, `DASH_DEFAULT_TELEGRAM_ID` (optional), `DASH_SESSION_SECRET`, later `DASH_TELEGRAM_LOGIN`.

## Alternatives considered

| Alternative | Rejected because |
|---|---|
| Shared secret + `X-Telegram-Id` | Impersonation; R1/COMMIT ban |
| Open local-only (no auth) | Accidental deploy leaks all rules/fires |
| Full Telegram Login before Pass 1 | Blocks read-only watchlist on domain/HTTPS setup |
| Secret-in-cookie | Couples ops credential to XSS/CSRF |
