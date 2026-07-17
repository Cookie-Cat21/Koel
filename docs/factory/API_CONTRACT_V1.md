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
| CSRF | Bootstrap at login: session cookie + CSRF cookie and/or `csrf_token` in JSON. All mutating methods require matching `X-CSRF-Token` **except** login (`POST /auth/demo`, later `/auth/telegram`). **`POST /auth/logout` requires CSRF** (no exemption). See [ADR 001 § CSRF](../adr/001-dash-auth.md). **Check order (E10-A01):** session is validated **before** CSRF. If both would fail (no/invalid session **and** missing/mismatched `X-CSRF-Token`), respond **`401 unauthorized`** — never `400 csrf_failed` without a valid session. |
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
| 403 | `forbidden`, `demo_auth_disabled`, `demo_auth_denied` |
| 404 | `not_found` |
| 409 | reserved; prefer idempotent return-existing over conflict for duplicate alerts |
| 429 | `rate_limited` (auth endpoints) |
| 503 | `degraded` (health when DB/poller unhealthy) |

### Authz matrix

| Route class | Requirement |
|---|---|
| `POST /auth/demo` | Public (demo gated by env); CSRF-exempt |
| `POST /auth/logout` | Valid session + CSRF |
| `GET /me`, watchlist, alerts, symbols (list + detail), disclosures, history, market movers, sectors | Valid session |
| Mutating watchlist/alerts | Valid session + CSRF |
| `GET /health` | Valid session; **full detail** only for `DASH_OPS_TELEGRAM_IDS` (others get summary) |

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

**Errors:** `403 demo_auth_disabled` · `403 demo_auth_denied` (unknown / empty allowlist — same shape) · `400 validation_error` · `429 rate_limited`

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

`status` is `"ok"` \| `"degraded"`. Omit or null `poller` when `HEALTH_URL` is unset and only DB liveness is available. When proxying poller loopback health, any explicit poller failure flag (`last_tick_ok === false`, `price_poll_ok === false`, or `disclosure_poll_ok === false`) MUST make the response `503` with `status: "degraded"`, even if `db_ok` is true. Forward `watched_missing` (string[]) and `circuits` (endpoint → breaker snapshot) when present. Do not expose this payload anonymously without an explicit future public-liveness subset (`status` + `db_ok` only).

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
  "name": "John Keells Holdings PLC",
  "created": true
}
```

Idempotent: if already on the watchlist, return `200` with `created: false` (same soft-messaging pattern as DELETE `removed: false`) — never hard `409`.

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

### `alert_log` delivery-state contract (ops/debugging)

Storage does **not** have a `delivery_state` enum column. For dashboards,
runbooks, and ad-hoc SQL, derive state from the real `alert_log` columns in
`db/migrations/001_initial.sql` through `009_alert_log_deferred_attempts.sql`:

| Column | Meaning |
|---|---|
| `message_sent` | Final UI/audit flag: the normal Telegram success path completed `mark_alert_sent`. |
| `attempt_count` | Count of hard (non-flood-control) Telegram send failures recorded by `mark_alert_attempt`. Dead-letters at `MAX_SEND_ATTEMPTS` (5). |
| `deferred_attempt_count` | Count of Telegram `RetryAfter` flood-control defers recorded by `mark_alert_deferred_attempt` (migration `009`). Kept separate from `attempt_count` so alternating ordinary failures and flood-waits don't burn down the tighter ceiling meant only for the former. Dead-letters at `MAX_DEFERRED_ATTEMPTS` (30). |
| `dead_lettered` | Terminal abandon flag. Excluded from future unsent claims. |
| `delivery_attempted_ok` | Telegram accepted delivery before `message_sent` was durably marked. Excluded from unsent claims to prevent duplicate pushes after restart. |
| `delivery_lease_until` | Short in-flight claim lease. Claimers skip the row until this is null or expired. |

Derived states, in precedence order:

| State | Predicate | Retry / claim behavior | Ops note |
|---|---|---|---|
| `sent` | `message_sent = TRUE` | Terminal; not claimable. | Normal success. `mark_alert_sent` also sets `delivery_attempted_ok = TRUE` and clears any lease. |
| `dead-letter` | `message_sent = FALSE AND dead_lettered = TRUE` | Terminal; not claimable. | Attempts exhausted or final send-mark persistence was abandoned. The reason is in logs (`alert_dead_lettered.reason = failed \| deferred`), and now also inferable from whether `attempt_count` or `deferred_attempt_count` reached its ceiling. If `delivery_attempted_ok = TRUE`, Telegram may already have accepted the message; do not manually resend. |
| `delivered-unmarked` | `message_sent = FALSE AND dead_lettered = FALSE AND delivery_attempted_ok = TRUE` | Not claimable. | Telegram returned OK, but the later `message_sent` update did not complete. Treat as delivered for duplicate-prevention; investigate `mark_alert_sent_failed` / `mark_alert_sent_abandoned`. |
| `leased` | `message_sent = FALSE AND dead_lettered = FALSE AND delivery_attempted_ok = FALSE AND delivery_lease_until >= now()` | Temporarily not claimable. | A poller has claimed the row for Telegram I/O. Lease clears on success/failure/defer, or naturally expires. |
| `deferred` | Same predicate as `unsent`, with `deferred_attempt_count > 0` and recent logs showing `alert_send_deferred`. | Claimable when no active lease. Dead-letters at `MAX_DEFERRED_ATTEMPTS` (30), tracked independently of `attempt_count`. | A second `RetryAfter` on the same send attempt (still-active flood control) also lands here rather than counting as a hard failure. |
| `unsent` | `message_sent = FALSE AND dead_lettered = FALSE AND delivery_attempted_ok = FALSE AND (delivery_lease_until IS NULL OR delivery_lease_until < now())` | Claimable by `claim_unsent_batch` while the rule remains active. | Includes never-attempted rows (`attempt_count = 0 AND deferred_attempt_count = 0`) and retryable failures. Hard failures dead-letter at `MAX_SEND_ATTEMPTS` (5). |

`claim_unsent_batch` additionally requires the joined `alert_rules.active = TRUE`
and uses `FOR UPDATE SKIP LOCKED` before setting a new `delivery_lease_until`.
The dashboard history API may continue returning raw `message_sent` for v1; if
it adds a label for ops, it must use the derived states above.

---

## Symbols / market data (read, Postgres)

UI must not render a Level-1 quote board from optional OHLC fields. Contract surfaces a slim `last` for the page; extra DB columns may exist but are not required for v1 UI.

### `GET /api/v1/symbols`

Thin market browse list (Tijori/CSE Phase 1). Session required. Postgres only — latest `price_snapshots` via **INNER JOIN** (symbols with no tick omitted). UI `/market` calls with `limit=100&sort=change_pct` (+ optional `q`).

Query:

| Param | Default | Notes |
|---|---|---|
| `limit` | `50` | Max `200` |
| `offset` | `0` | |
| `q` | — | Optional symbol/name substring (case-insensitive) |
| `sort` | `change_pct` | `change_pct` (desc, nulls last) or `symbol` (asc) |

**Response** `200`

```json
{
  "items": [
    {
      "symbol": "JKH.N0000",
      "name": "John Keells Holdings PLC",
      "sector": null,
      "price": 22.5,
      "change": 0.3,
      "change_pct": 1.35,
      "ts": "2026-07-11T09:00:00+00:00"
    }
  ],
  "limit": 50,
  "offset": 0,
  "sort": "change_pct",
  "q": null
}
```

Fence: discovery list for watchlist setup — not a screener or OHLC board. See [TIJORI_CSE_PLAN.md](TIJORI_CSE_PLAN.md).

### `GET /api/v1/market/movers`

Thin top gainers/losers peek for `/market` (Tijori/CSE Phase 1). Session required.
Reuses the same Postgres browse query as `GET /api/v1/symbols` (latest
`price_snapshots` via **INNER JOIN**). Sign-filtered so gainers/losers cannot
mislabel flats or opposite moves. No cse.lk. Not a screener — no `q` / sector /
volume / multi-sort filters.

Query:

| Param | Default | Notes |
|---|---|---|
| `direction` | `up` | `up` (change_pct > 0, sort desc) or `down` (change_pct < 0, sort asc). Other values → `400` `validation_error`. |
| `limit` | `20` | Max `50` |

**Response** `200`

```json
{
  "items": [
    {
      "symbol": "JKH.N0000",
      "name": "John Keells Holdings PLC",
      "sector": null,
      "price": 22.5,
      "change": 0.3,
      "change_pct": 1.35,
      "ts": "2026-07-11T09:00:00+00:00"
    }
  ],
  "direction": "up",
  "limit": 20
}
```

Item shape matches `GET /api/v1/symbols` browse rows. UI calls
`?direction=up&limit=5` and `?direction=down&limit=5` for the top-movers strip.

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
      "company_name": "John Keells Holdings PLC",
      "pdf_url": "https://cdn.cse.lk/uploadAnnounceFiles/….pdf",
      "brief": "Interim results summary…",
      "brief_status": "ready"
    }
  ]
}
```

Both DB `id` and `external_id` are required in the payload (resolves IA↔WAVE naming drift).

#### Brief fields (`pdf_url`, `brief`, `brief_status`)

| Field | Source | Notes |
|---|---|---|
| `pdf_url` | `disclosures.pdf_url` | CDN-allowlisted egress (`https://cdn.cse.lk/…`); unsafe/off-allowlist → `null`. |
| `brief` | `disclosure_briefs.brief` | Plain text; **only egresses when `brief_status === "ready"`** (else `null`, even if a draft row exists). Caps/strips controls on egress. |
| `brief_status` | `disclosure_briefs.status` | LEFT JOIN; `null` when no brief row. |

When no `disclosure_briefs` row exists, `pdf_url` may still be set (enricher), but
`brief` and `brief_status` are `null`.

#### Processing status (`brief_status` enum)

DB check constraint (`007_brief_processing_status.sql`) and dash egress allowlist
are identical. `brief_status` is one of:

| Status | Meaning |
|---|---|
| `pending` | Queued for the briefs worker (AI enabled at enqueue). |
| `processing` | Claimed/leased by a worker drain; in-flight. Stale `processing` rows are reclaimable after the lease window. |
| `ready` | Brief text available; only status where API/`brief` egress is non-null and UI may render the summary. |
| `failed` | Worker failed; `brief` stays null. |
| `skipped` | Enqueued while AI briefs were off (`AI_BRIEFS_ENABLED=0`); may later promote to `pending`. |

Unknown/invalid DB values normalize to `null` on egress. Dash UI prefers
`pdf_url` over `url` for the filing link and renders `brief` only when
`brief_status === "ready"`.

### Disclosure alert gating (bot / poller — E11-A01)

Telegram `/alert SYMBOL disclosure` and the poller’s rule engine **fail closed**
on publish time:

- Prefer CSE `createdDate` (epoch ms) as `published_at` for gating.
- Missing / non-positive `createdDate` → `published_at` forced to Unix epoch
  (1970-01-01) so the filing is treated as stale and does **not** fire.
- Rules also skip when `published_at <= rule.created_at` (no historical backfill
  flood). Missing `rule.created_at` → no fire.

Dash `GET .../disclosures` still returns stored rows for display; gating above
applies only to alert fire paths.

---

## Sectors (optional ingest)

### `GET /api/v1/sectors`

Session required. Reads latest upserted rows from Postgres `sectors` (populated
only when the poller runs with `SECTORS_INGEST=1`). Empty `items` when ingest
has never run. No cse.lk from the dash.

**Response** `200`

```json
{
  "items": [
    {
      "sector_id": 223,
      "symbol": "EGY",
      "name": "Energy",
      "index_code": "1010",
      "index_name": "S&P/CSE Energy Industry Group Index",
      "index_value": 2951.6,
      "change": -67.62,
      "change_pct": -2.24,
      "volume_today": 74378,
      "turnover_today": 9844386.05,
      "previous_close": 3019.22,
      "ts": "2026-07-11T09:00:00+00:00"
    }
  ]
}
```

Not a sector heatmap/screener — list + performance fields only.

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
| `GET` | `/api/v1/symbols` | Market browse list (slim) |
| `GET` | `/api/v1/market/movers` | Thin gainers/losers (`direction` + `limit`) |
| `GET` | `/api/v1/symbols/{symbol}` | Slim `last` |
| `GET` | `/api/v1/symbols/{symbol}/snapshots` | |
| `GET` | `/api/v1/symbols/{symbol}/disclosures` | `id` + `external_id` + brief fields (`brief_status` includes `processing`) |
| `GET` | `/api/v1/sectors` | Optional sector board (Postgres; needs `SECTORS_INGEST=1`) |

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
| Disclosure brief fields | `pdf_url` + `brief` + `brief_status`; brief text only when `ready` |
| Brief processing status | `pending` \| `processing` \| `ready` \| `failed` \| `skipped` |
| Market movers | `GET /api/v1/market/movers` thin sign-filtered peek (not a screener) |
| Sectors | `GET /api/v1/sectors` optional Postgres board (`SECTORS_INGEST=1`) |
| Symbol `last` | Slim fields for UI; no OHLC board requirement |

---

## Explicit non-goals

- Portfolio / P&L / tax / screener / TA endpoints  
- WebSocket quote streams  
- Resend-Telegram or fire analytics  
- Deploy/restart controls on health  
- OpenAPI codegen requirement for Pass 1 (this markdown is enough to implement)
