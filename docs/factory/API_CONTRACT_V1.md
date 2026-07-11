# Chime Dashboard API Contract v1

**Status:** Frozen (WS-024)  
**Base path:** `/api/v1`  
**Auth:** [ADR 001 — Dashboard authentication](../adr/001-dash-auth.md)  
**IA:** [DASH_IA.md](DASH_IA.md)  
**Schema:** `db/migrations/001_initial.sql`  
**Host (locked for implementers):** Next.js Route Handlers under `web/` reading Postgres via `DATABASE_URL`. No cse.lk from `web/`.

This document is the single source of truth for dash REST shapes. WAVE1_DASH `/api/*` sketches without `v1`, `/alerts/fires`, and Bearer+`X-Telegram-Id` are superseded.

---

## Global conventions

| Rule | Detail |
|---|---|
| Content type | `application/json; charset=utf-8` |
| Auth | Signed HttpOnly session cookie after login ([ADR 001](../adr/001-dash-auth.md)). `user_id` is taken from the session only. |
| CSRF | Bootstrap at login: session cookie + CSRF cookie and/or `csrf_token` in JSON. All mutating methods require matching `X-CSRF-Token` **except** login (`POST /auth/demo`, later `/auth/telegram`). **`POST /auth/logout` requires CSRF** (no exemption). See [ADR 001 § CSRF](../adr/001-dash-auth.md). |
| Symbols | Uppercase; same regex as bot (`SYMBOL_RE`). Invalid → `400` `invalid_symbol`. |
| Timestamps | ISO-8601 UTC strings. |
| NFA | **UI-only.** API returns raw facts; clients render `disclaimer()` chrome. |
| Pagination | Query `limit` (default documented per route, max 200) and optional `cursor` / `offset` where noted. |
| No WebSocket | v1 is request/response; pages refresh on navigation. |
| Storage parity | Mutations mirror `chime.storage` / bot: auto-watch on alert create; unwatch deactivates rules for that symbol; cancel = soft `active=false`; duplicate active alerts → **idempotent return existing** (not deactivate-then-insert; not hard 409). |

### Error envelope

All non-2xx JSON errors:

```json
{
  "error": {
    "code": "unauthorized",
    "message": "Authentication required."
  }
}
```

| HTTP | `code` (examples) |
|---|---|
| 400 | `invalid_symbol`, `validation_error`, `csrf_failed` |
| 401 | `unauthorized` |
| 403 | `forbidden`, `demo_auth_disabled`, `telegram_id_not_allowlisted` |
| 404 | `not_found` |
| 409 | reserved; prefer idempotent return-existing over conflict for duplicate alerts |
| 503 | `degraded` (health when DB/poller unhealthy) |

### Authz matrix

| Route class | Requirement |
|---|---|
| `POST /auth/demo` | Public (demo gated by env); CSRF-exempt |
| `POST /auth/logout` | Valid session + CSRF |
| `GET /me`, watchlist, alerts, symbols, disclosures, history | Valid session |
| Mutating watchlist/alerts | Valid session + CSRF |
| `GET /health` | **Ops-gated** (valid session in v1 demo; not anonymously public by default) |

---

## Auth

### `POST /api/v1/auth/demo`

Demo only (`DASH_DEMO_AUTH=1` + allowlist). See ADR 001.

**Request**

```json
{ "telegram_id": 123456789 }
```

**Response** `200`

```json
{
  "user": {
    "id": 1,
    "telegram_id": 123456789
  }
}
```

Sets `Set-Cookie: chime_session=…; HttpOnly; Secure; SameSite=Lax; Path=/` **and** CSRF material (non-HttpOnly CSRF cookie and/or `csrf_token` in the JSON body). See ADR 001 § CSRF.

**Errors:** `403 demo_auth_disabled` · `403 telegram_id_not_allowlisted` · `400 validation_error`

### `POST /api/v1/auth/telegram` *(future — stub only until enabled)*

Telegram Login Widget payload verified server-side; response same shape as demo. Stub must not accept `hash` before `DASH_TELEGRAM_LOGIN=1`.

### `POST /api/v1/auth/logout`

Requires valid session + matching `X-CSRF-Token` (no CSRF exemption).

**Response** `200`

```json
{ "ok": true }
```

Clears session cookie (and CSRF cookie if used).

### `GET /api/v1/me`

**Response** `200`

```json
{
  "id": 1,
  "telegram_id": 123456789,
  "created_at": "2026-07-01T10:00:00+00:00"
}
```

May also return CSRF material if not using a separate endpoint:

```json
{
  "id": 1,
  "telegram_id": 123456789,
  "created_at": "2026-07-01T10:00:00+00:00",
  "csrf_token": "…"
}
```

---

## Health (ops-gated)

### `GET /api/v1/health`

Requires authenticated session (v1). Prefer proxying poller health and/or DB ping — **one** source of truth; do not invent conflicting fields.

**Response** `200` (healthy) or `503` (degraded)

```json
{
  "status": "ok",
  "db_ok": true,
  "started_at": "2026-07-11T03:30:00+00:00",
  "last_snapshot_at": "2026-07-11T09:00:00+00:00",
  "poller": {
    "last_tick_at": "2026-07-11T09:00:00+00:00",
    "last_tick_ok": true,
    "price_poll_ok": true,
    "disclosure_poll_ok": true,
    "lock_held_skip": false,
    "last_error": null,
    "watched_missing": [],
    "circuits": {}
  }
}
```

`status` is `"ok"` \| `"degraded"`. Omit or null `poller` when `HEALTH_URL` is unset and only DB liveness is available. When proxying poller loopback health, forward `watched_missing` (string[]) and `circuits` (endpoint → breaker snapshot) when present. Do not expose this payload anonymously without an explicit future public-liveness subset (`status` + `db_ok` only).

---

## Watchlist

Bot parity: `/watch`, `/unwatch`. Unwatch **deactivates** active rules for that symbol (`deactivate_rules_for_symbol`).

### `GET /api/v1/watchlist`

**Response** `200`

```json
{
  "items": [
    {
      "symbol": "JKH.N0000",
      "name": "John Keells Holdings PLC",
      "sector": "Diversified Financials",
      "price": 22.5,
      "change": 0.3,
      "change_pct": 1.35,
      "ts": "2026-07-11T09:00:00+00:00"
    }
  ]
}
```

Latest `price_snapshots` join (e.g. `DISTINCT ON (symbol)`). Missing snapshot → `price`/`change`/`change_pct`/`ts` may be `null`.

### `POST /api/v1/watchlist`

**Request**

```json
{ "symbol": "JKH.N0000" }
```

**Response** `201` (or `200` if already watched)

```json
{
  "symbol": "JKH.N0000",
  "name": "John Keells Holdings PLC"
}
```

**Postgres only:** symbol must already exist in `stocks` (poller/bot upserted) **or** be accepted as a normalized symbol with a `stocks` stub row if product chooses upsert-without-CSE — **never** call cse.lk from this handler. Prefer: require known `stocks` row → `404 not_found` if unknown.

### `DELETE /api/v1/watchlist/{symbol}`

**Response** `200`

```json
{
  "removed": true,
  "deactivated_alerts": 2
}
```

If not on watchlist: `removed: false`, still report `deactivated_alerts` count (usually `0`), or `404` if preferred — **implementers pick one**; recommended: `200` with `removed: false` to match bot soft messaging. Always run rule deactivation for the symbol.

---

## Alerts

Bot parity: `/alert …`, `/cancel ALERT_ID`, `/myalerts` (active only).

`type` enum: `price_above` \| `price_below` \| `daily_move` \| `disclosure`  
`threshold`: required number except `disclosure` (`null`).

### `GET /api/v1/alerts`

Query: `active` default `true` (omit or `?active=true`). `?active=false` may list cancelled rules; Pass 1 UI shows active only.

**Response** `200`

```json
{
  "rules": [
    {
      "id": 42,
      "symbol": "JKH.N0000",
      "type": "price_above",
      "threshold": 25.0,
      "active": true,
      "armed": true,
      "created_at": "2026-07-10T08:00:00+00:00"
    }
  ]
}
```

### `POST /api/v1/alerts`

**Request**

```json
{
  "symbol": "JKH.N0000",
  "type": "price_above",
  "threshold": 25.0
}
```

Disclosure example:

```json
{
  "symbol": "JKH.N0000",
  "type": "disclosure"
}
```

**Response** `201` — created rule object (same fields as list item).

**Semantics (mirror `Storage.create_alert_rule`):** ensure stock row from Postgres (404 if unknown — no CSE from web); **auto-add watchlist**; if an identical active rule exists, **return it**; else insert `armed=true`. Concurrent inserts: loser catches unique violation and returns the survivor.

### `DELETE /api/v1/alerts/{id}` — cancel by id

Soft cancel: `active=false`. Maps to bot `/cancel ALERT_ID`. **Not** `PATCH` (WAVE sketch rejected).

**Response** `200`

```json
{ "cancelled": true }
```

Already inactive / missing / wrong user → `cancelled: false` with `200`, or `404 not_found`. Recommended: `404` when id not owned by session user.

---

## Alert history

UI route: `/alerts/history` (nav label **History**, not “Fires”).

### `GET /api/v1/alerts/history`

Query: `symbol` (optional), `limit` (default `50`, max `200`), `offset` (default `0`).

**Response** `200`

```json
{
  "events": [
    {
      "id": 1001,
      "rule_id": 42,
      "symbol": "JKH.N0000",
      "type": "price_above",
      "fired_at": "2026-07-11T09:05:00+00:00",
      "message_sent": true,
      "message_text": "JKH.N0000 crossed above 25.0 (now 25.4).",
      "event_key": "price_above:42:2026-07-11T09:00:00+00:00"
    }
  ],
  "limit": 50,
  "offset": 0
}
```

Join `alert_log` → `alert_rules` scoped to session `user_id`. Path is **`/alerts/history`**, not `/alerts/fires`.

---

## Symbols / market data (read, Postgres)

UI must not render a Level-1 quote board from optional OHLC fields. Contract surfaces a slim `last` for the page; extra DB columns may exist but are not required for v1 UI.

### `GET /api/v1/symbols/{symbol}`

**Response** `200`

```json
{
  "symbol": "JKH.N0000",
  "name": "John Keells Holdings PLC",
  "sector": "Diversified Financials",
  "last": {
    "price": 22.5,
    "change": 0.3,
    "change_pct": 1.35,
    "volume": 120000,
    "ts": "2026-07-11T09:00:00+00:00"
  }
}
```

`last` may be `null` if no snapshots. Do not require `high` / `low` / `open` / `market_cap` in the API response for v1 UI.

### `GET /api/v1/symbols/{symbol}/snapshots`

Query: `limit` (default `60`, max `200`).

**Response** `200`

```json
{
  "points": [
    {
      "ts": "2026-07-11T08:00:00+00:00",
      "price": 22.1,
      "change_pct": 0.5
    }
  ]
}
```

Ordered by `ts` ascending (sparkline-friendly) or descending — **ascending** locked for chart polyline.

### `GET /api/v1/symbols/{symbol}/disclosures`

Query: `limit` (default `20`, max `100`).

**Response** `200`

```json
{
  "items": [
    {
      "id": 55,
      "external_id": "ann-98765",
      "title": "Interim Financial Statements",
      "category": "Financial Report",
      "url": "https://www.cse.lk/…",
      "published_at": "2026-07-10T04:00:00+00:00",
      "company_name": "John Keells Holdings PLC"
    }
  ]
}
```

Both DB `id` and `external_id` are required in the payload (resolves IA↔WAVE naming drift).

---

## Route index (frozen)

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/auth/demo` | Allowlist demo login |
| `POST` | `/api/v1/auth/telegram` | Future |
| `POST` | `/api/v1/auth/logout` | Clear session (session + CSRF) |
| `GET` | `/api/v1/me` | Current user (+ optional CSRF) |
| `GET` | `/api/v1/health` | Ops-gated |
| `GET` | `/api/v1/watchlist` | |
| `POST` | `/api/v1/watchlist` | No cse.lk |
| `DELETE` | `/api/v1/watchlist/{symbol}` | Returns `deactivated_alerts` |
| `GET` | `/api/v1/alerts` | Default active only |
| `POST` | `/api/v1/alerts` | Auto-watch; idempotent return-existing on duplicates |
| `DELETE` | `/api/v1/alerts/{id}` | Soft cancel by id |
| `GET` | `/api/v1/alerts/history` | Not `/fires` |
| `GET` | `/api/v1/symbols/{symbol}` | Slim `last` |
| `GET` | `/api/v1/symbols/{symbol}/snapshots` | |
| `GET` | `/api/v1/symbols/{symbol}/disclosures` | `id` + `external_id` |

---

## R1_DASH inconsistency resolutions

| Topic | Frozen choice |
|---|---|
| Auth | Server session after allowlisted demo (or future Telegram Login) — **not** Bearer + client `telegram_id` |
| API prefix | `/api/v1` |
| Fire history | `/api/v1/alerts/history` + UI `/alerts/history` (History) |
| Cancel alert | `DELETE /api/v1/alerts/{id}` soft `active=false` |
| Unwatch | JSON includes `deactivated_alerts` |
| Health | Ops-/session-gated; not demo-open by default |
| Error envelope | `{ "error": { "code", "message" } }` |
| NFA | UI-only |
| API host | Next Route Handlers + Postgres |
| Watchlist validate | Against Postgres `stocks` / poller data — **no** dash→cse.lk |
| Disclosure ids | Both `id` and `external_id` |
| Symbol `last` | Slim fields for UI; no OHLC board requirement |

---

## Explicit non-goals

- Portfolio / P&L / tax / screener / TA endpoints  
- WebSocket quote streams  
- Resend-Telegram or fire analytics  
- Deploy/restart controls on health  
- OpenAPI codegen requirement for Pass 1 (this markdown is enough to implement)
