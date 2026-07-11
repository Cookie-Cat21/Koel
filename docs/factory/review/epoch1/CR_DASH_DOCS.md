# CR_DASH_DOCS — Epoch 1 code review (dash auth / API docs)

**Reviewer role:** Docs CR (accurate only; no `web/` code expected yet)  
**Scope:** `docs/adr/001-dash-auth.md`, `docs/factory/API_CONTRACT_V1.md`, `docs/factory/DASH_IA.md` (auth + API sections)  
**Date:** 2026-07-11  
**Context:** Post WS-023 / WS-024 freeze; checks remaining inconsistencies, ADR security holes, CSRF gaps, Postgres-only promise, impersonation misread risks.

---

## Verdict

**CONDITIONAL PASS — contracts largely converged; do not treat as implementer-safe without patching residual IA drift and CSRF underspec.**

ADR 001 + `API_CONTRACT_V1.md` correctly kill Bearer + client `telegram_id`, lock `/api/v1`, session→`user_id`, and “no cse.lk from `web/`.” That closes the R1_DASH ship-gate for auth/API **shape**.

Remaining risk is not another WAVE fork — it is **implementers following stale IA sentences** (CSE validate, FastAPI host, login “token”) and **CSRF/login bootstrap that is specified in three incompatible ways**. Fix docs before Pass 1 write routes; read-only Pass 1 can proceed if agents cite ADR + contract only and ignore IA §6 / implementation notes.

---

## Ranked findings

### P0 — Fix before any mutating dash route

| # | Finding | Evidence | Risk if misread |
|---|---|---|---|
| 1 | **IA parity rule still says “validate symbol via CSE”** | `DASH_IA.md` §6: “same storage semantics as the bot (**validate symbol via CSE**, upsert stock, …)” | Implementer adds a second cse.lk client from `web/` or Route Handlers — exact fence/compliance NO-GO R1_COMPLIANCE flagged. Contract + ADR say Postgres only; **IA §6 is the live contradiction.** |
| 2 | **CSRF exemption set disagrees (logout)** | ADR: mutating `/api/v1/*` must CSRF **except login itself**. Contract: except `POST /auth/demo` **and** `POST /auth/logout` (“CSRF-safe preferred”). | One agent ships CSRF on logout; another skips. Logout CSRF is low blast radius; the inconsistency trains “exceptions are flexible” — dangerous for watchlist/alert writes. |
| 3 | **CSRF token bootstrap not locked** | ADR allows double-submit **or** synchronizer at login / `GET /me` / `GET /auth/csrf`. Demo `200` body in contract has **no** `csrf_token`. `/me` marks CSRF “optional.” `GET /auth/csrf` is not in the frozen route index. | Pass 2 agent invents a third shape, or ships mutations with “SameSite is enough” (ADR forbids that verbally but gives no single required mechanism). |

### P1 — Security / impersonation misread (ADR wording)

| # | Finding | Evidence | Risk if misread |
|---|---|---|---|
| 4 | **“Alone” qualifier weakens the ban** | ADR canonical #2: never derive identity from client `telegram_id` header/query **alone**. Banned table: shared secret + client id **as sole auth**. | Implementer keeps session **and** accepts `X-Telegram-Id` / body `telegram_id` as override (“admin debug”). That restores universal impersonation under a session cookie. **Ban must be: never trust client telegram_id for authz after login; session `user_id` only.** |
| 5 | **Demo allowlist is identity, not a secret — no deploy fail-closed** | `POST /auth/demo` is public when `DASH_DEMO_AUTH=1`. Allowlisted numeric IDs are guessable/leaked from UI and `/me`. ADR says staging-only / drop demo in production, but only `DASH_SESSION_SECRET` is fail-closed-empty; **empty or wildcard `DASH_DEMO_TELEGRAM_IDS` parsing is unspecified.** | Public deploy with demo on = anyone who knows an allowlisted id owns that user’s watchlist/alerts/fires. Empty allowlist must refuse all demo logins; document “never enable demo on a public URL.” |
| 6 | **Health “or separate ops credential” invites secret revival** | ADR health: session **or** “a separate ops credential documented in the API contract.” Contract documents **session only** — no ops credential shape. | Implementer reintroduces `DASH_API_SECRET` Bearer for `/health`, then reuses it elsewhere. ADR already bans secret-in-cookie and Bearer+telegram_id; an underspecified “ops credential” is the back door. **Either delete the clause or freeze one non-impersonating probe token in the contract.** |
| 7 | **Login wireframe still says “token”** | `DASH_IA.md` `/login`: “demo user select / **token**.” ADR: no “paste operator secret” as identity. | Agents rebuild WAVE’s paste-`DASH_API_SECRET` login UX. |

### P2 — Postgres-only promise cracks / contract soft spots

| # | Finding | Evidence | Risk if misread |
|---|---|---|---|
| 8 | **Watchlist POST still offers stub-upsert waffle** | Contract: known `stocks` row **or** “normalized symbol with a `stocks` stub row if product chooses upsert-without-CSE”; Prefer `404` if unknown. | Two implementations (strict vs invent-stub). Stub path is Postgres-only (OK for fence) but breaks bot parity and poller assumptions if dash creates symbols the poller never tracks. **Lock one:** prefer `404 not_found` for unknown symbols. |
| 9 | **IA host note still offers FastAPI** | `DASH_IA.md` implementation notes: “Prefer thin FastAPI/Starlette (or Next Route Handlers…)”. Contract **locks** Next Route Handlers + `DATABASE_URL`. | Dual-host thrash; second process that “helpfully” calls CSE adapters. |
| 10 | **Health UI field names ≠ contract payload** | IA `/health` wireframe: `last_poll_at`, `last_poll_ok`, `symbols_polled`, `errors`. Contract: `last_snapshot_at`, nested `poller.last_tick_*`, `last_error`, no `symbols_polled`. | UI invents fields or probes poller directly instead of the frozen JSON. |

### P3 — Smaller consistency / hygiene

| # | Finding | Notes |
|---|---|---|
| 11 | **Any-session health = ops detail for every demo user** | Acceptable for single-operator v1; document that future multi-user must not grant full `last_error` / tick flags to all sessions (or keep health out of primary nav). |
| 12 | **Signed cookie may embed `user_id`** | ADR allows opaque id **or** signed token with `user_id`. Fine if HMAC + expiry + rotation; note lack of server-side revoke list until logout/TTL. Not a hole if TTL short; don’t also embed unsigned trust anchors. |
| 13 | **`ensure_user` on allowlisted demo** | Correctly limited; still creates bot-visible `users` rows without Telegram proof. Staging-only warning is present — keep it in `.env.example` when `web/` scaffolds. |
| 14 | **Contract marks logout “Public”** | Correct for cookie clear; must still bind clear to the presented session cookie (not a body `telegram_id`). Unstated but implied — spell out “logout ignores body identity fields.” |

---

## Cross-doc matrix (auth / API only)

| Topic | ADR 001 | API_CONTRACT_V1 | DASH_IA (auth/API) | Status |
|---|---|---|---|---|
| Session after login; `user_id` from session | Yes | Yes | Yes (§3–4) | Aligned |
| Ban Bearer + `X-Telegram-Id` sole auth | Yes | Yes (superseded) | Yes (banned) | Aligned; ADR “alone” weasel remains |
| CSRF on writes | Mandatory (except login) | Except demo **+ logout** | “CSRF required on mutations” (no logout exception) | **Split** |
| CSRF bootstrap | login / me / csrf endpoint / double-submit | Optional on `/me`; not on demo response; no `/auth/csrf` route | Optional on `/me` | **Underspecified** |
| No cse.lk from `web/` | Yes | Yes (locked) | Yes in §3–4; **§6 CSE validate** | **IA §6 break** |
| API host | (points at contract) | Next Route Handlers locked | FastAPI *or* Next in notes | **IA notes break** |
| Health gate | Session **or** ops credential | Session only (v1) | Session | **ADR extra door** |
| Demo allowlist | Required | 403 codes | Env table in §4 | Aligned; empty-list fail-closed missing |
| `/alerts/history` not `/fires` | — | Frozen | Frozen | Aligned |
| Error envelope | — | `{ error: { code, message } }` | Same | Aligned |
| NFA | — | UI-only | UI-only | Aligned |

---

## Impersonation checklist for implementers (read this, not WAVE)

1. After login, **never** read `telegram_id` / `X-Telegram-Id` / query `telegram_id` to choose the row to mutate — only `session.user_id`.
2. Demo `POST /auth/demo` may accept `telegram_id` **only** to map allowlist → `users.id`, then mint session; subsequent requests ignore client ids.
3. Do not put `DASH_API_SECRET` (or any ops secret) in cookies, localStorage, or CSRF tokens.
4. Do not implement “session OR bearer secret + telegram_id” dual mode.
5. Stub `POST /auth/telegram` must reject bodies with `hash` until `DASH_TELEGRAM_LOGIN=1` and real verify.

---

## CSRF checklist gap (what docs still owe)

| Item | Required before first `POST/DELETE` watchlist/alerts |
|---|---|
| Single mechanism | Pick **one**: synchronizer token **or** double-submit; document it in the contract |
| Issue point | Return CSRF material on successful demo login **and/or** mandatory `GET /me` / `GET /auth/csrf` — not “optional” |
| Header name | Freeze `X-CSRF-Token` (already exampled) |
| Logout | Either require CSRF (match ADR) **or** amend ADR to match contract and state SameSite+POST-only logout |
| Failure | `400 csrf_failed` already listed — keep |

---

## What is already good (do not regress)

- WAVE Bearer + client `telegram_id` explicitly superseded and banned.
- HttpOnly + Secure + SameSite; no secret-in-cookie; no localStorage session.
- Session rotation on login (anti-fixation) stated.
- Telegram widget stub must not accept forged `hash`.
- Deny-by-default CORS / same-origin v1.
- Health not anonymously public by default; full poller detail gated.
- Disclosure payload requires both `id` and `external_id`.
- Storage soft-replace / unwatch deactivate / cancel soft-delete parity called out in contract.

---

## Recommended doc patches (no code)

1. **DASH_IA §6:** replace “validate symbol via CSE” with “validate against Postgres `stocks` / poller data — never cse.lk from `web/`.”
2. **DASH_IA `/login`:** drop “token”; say “allowlisted demo Telegram ID.”
3. **DASH_IA implementation notes:** delete FastAPI preference; point at contract host lock.
4. **DASH_IA `/health` wireframe:** align field names to contract `poller` object.
5. **ADR ↔ contract:** one CSRF exemption list; one health auth story; reword “alone” → never trust client telegram_id for authz.
6. **Contract:** fail-closed empty `DASH_DEMO_TELEGRAM_IDS` when demo enabled; lock watchlist unknown-symbol → `404`; freeze CSRF bootstrap on login or dedicated route.

---

## Reviewer note

Epoch 1 docs **did** the important job: one auth ADR, one frozen API contract, impersonation sketch dead. This CR is about **residual sentences that will recreate the old bugs** if an implementer skims IA instead of the contract. Accurate fix is editorial — not a new wave of product WS.
