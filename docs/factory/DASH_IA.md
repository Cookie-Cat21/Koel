# Chime Dashboard — Information Architecture & API Sketch

**Lane:** DASH · **Stack:** Next.js + Tailwind + shadcn/ui · **Scope:** thin management UI only  
**Constitution:** [COMMIT_FACTORY.md](COMMIT_FACTORY.md) §7 · [CLAUDE.md](../../CLAUDE.md)

Telegram remains the push channel. The dashboard is for CRUD + inspection — not a trading terminal.

---

## 1. Sitemap

| Route | Purpose | Auth |
|---|---|---|
| `/` | Redirect → `/watchlist` (or `/login` if unauthenticated) | — |
| `/login` | Local/demo sign-in (v1); Telegram Login Widget later | public |
| `/market` | Thin CSE symbol browse (latest snapshots from Postgres) | user |
| `/watchlist` | User watchlist + last price / change | user |
| `/alerts` | Active alert rules CRUD | user |
| `/alerts/history` | Fire history (`alert_log`) | user |
| `/symbols/[symbol]` | Symbol detail: last tick, sparkline, disclosures | user |
| `/health` | Ops: poller liveness / last poll (read-only) | ops-gated (session; see ADR 001) |

No nested app shell beyond a single top nav: Browse · Watchlist · Alerts · History · (Health).

**Browse fence:** `/market` is a slim discovery list (symbol · name · last · change_pct · link to symbol detail). Not a quote board, screener, or trading terminal. Data comes from poller-persisted `price_snapshots` only — no cse.lk from `web/`. See [TIJORI_CSE_PLAN.md](TIJORI_CSE_PLAN.md).

---

## 2. Wireframe notes (bullet layout)

### `/login`
- Brand wordmark “Chime” (hero-level, not nav-only)
- One line: manage watchlist & alerts; pushes still go to Telegram
- Primary CTA: sign in (demo user select / token)
- Footer NFA line
- No marketing sections, stats, or feature grids

### `/market`
- Header: “Browse” + search (symbol/name); subtitle: snapshots for watch discovery, alerts stay on Telegram
- Fetches `GET /api/v1/symbols?limit=100&sort=change_pct` (+ `q` when searching)
- Top movers strip (gainers/losers): one symbol+Watch link → `/symbols/[symbol]` (unique `aria-label`, no duplicate tab stops; no inline POST/JS), plus “Add via watchlist” note → `/watchlist`
- Sectors strip (optional): name + change_pct from `GET /api/v1/sectors`; list uses `aria-labelledby` the Sectors heading; truncated names keep `title`
- List rows: `symbol` (→ `/symbols/[symbol]`) · name · last `price` · `change_pct` · snapshot `ts`
- Sorted by `change_pct` desc by default (thin movers view — not a screener)
- Empty state: poller has not persisted tradeSummary yet (or no search match)
- NFA under price-adjacent copy + site footer
- Fence: no OHLC board, no multi-column sort UI, no live ticks, no cse.lk from `web/`

### `/watchlist`
- Header: “Watchlist” + add-symbol control (input + Add)
- List rows: `symbol` · name · last `price` · `change_pct` · link to symbol detail
- Row action: Unwatch
- Empty state: add one, browse `/market` for discovery, or use `/watch` in Telegram
- Mobile: stacked rows, full-width add form

### `/alerts`
- Header: “Alerts” + “New alert” form
- Form fields: symbol · type (`price_above` \| `price_below` \| `daily_move` \| `disclosure`) · threshold (hidden for disclosure)
- List rows: `#id` · symbol · type · threshold · armed/active badges · Cancel
- Empty state mirrors bot copy
- NFA under any price-adjacent copy

### `/alerts/history`
- Filter: symbol (optional), limit
- Rows: fired_at · symbol · type · trigger/message excerpt · message_sent
- No charts, no “P&L impact”

### `/symbols/[symbol]`
- Title: symbol + name + sector
- Last snapshot block: price, change, change_pct, volume, ts
- Sparkline: recent `price_snapshots` (price vs ts only — not TA)
- Disclosures list: published_at · title · category · external link; list uses `aria-labelledby` the Disclosures heading; filing links announce opens-in-new-tab
- Ready AI brief: labelled “Filing brief” group (`role="group"` + `aria-labelledby`) under the filing row — plain text only when `brief_status === ready`
- Shortcuts: Add to watchlist · New alert for this symbol

### `/health`
- status · started_at · last_poll_at · last_poll_ok · symbols_polled · errors (from poller health payload)
- No config editors, no restart controls in v1

---

## 3. API endpoints (REST)

**Canonical contract:** [API_CONTRACT_V1.md](API_CONTRACT_V1.md) (WS-024). Summary below — if anything conflicts, the contract wins.

Base: `/api/v1`. JSON request/response. User routes scoped by **session** `user_id` ([ADR 001](../adr/001-dash-auth.md)). Errors: `{ "error": { "code": string, "message": string } }`. CSRF required on mutations. **No cse.lk from `web/`.**

### Auth

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/api/v1/auth/demo` | `{ "telegram_id": number }` (allowlisted) | `{ "user": { "id", "telegram_id" } }` + HttpOnly session cookie |
| `POST` | `/api/v1/auth/telegram` *(future)* | Telegram Login Widget payload | same session shape as demo |
| `POST` | `/api/v1/auth/logout` | — | `{ "ok": true }` |
| `GET` | `/api/v1/me` | — | `{ "id", "telegram_id", "created_at" }` (+ optional `csrf_token`) |

### Watchlist

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/api/v1/watchlist` | — | `{ "items": [{ "symbol", "name", "sector", "price", "change", "change_pct", "ts" }] }` |
| `POST` | `/api/v1/watchlist` | `{ "symbol": string }` | `{ "symbol", "name" }` (Postgres `stocks` only — no CSE from dash) |
| `DELETE` | `/api/v1/watchlist/{symbol}` | — | `{ "removed": bool, "deactivated_alerts": number }` |

### Alerts

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/api/v1/alerts` | `?active=true` (default) | `{ "rules": [{ "id", "symbol", "type", "threshold", "active", "armed", "created_at" }] }` |
| `POST` | `/api/v1/alerts` | `{ "symbol", "type", "threshold"? }` | created/existing rule object (auto-watch; idempotent) |
| `DELETE` | `/api/v1/alerts/{id}` | — | `{ "cancelled": bool }` (soft: `active=false`; bot `/cancel`) |
| `GET` | `/api/v1/alerts/history` | `?symbol=&limit=50` | `{ "events": [{ "id", "rule_id", "symbol", "type", "fired_at", "message_sent", "message_text", "event_key" }] }` |

`type` enum: `price_above` \| `price_below` \| `daily_move` \| `disclosure`  
`threshold` required except `disclosure` (null). Mirror bot: unwatch deactivates rules for that symbol.

### Symbols / market data (read)

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/api/v1/symbols` | `?limit=&offset=&q=&sort=` | `{ "items": [{ "symbol", "name", "sector", "price", "change", "change_pct", "ts" }], "limit", "offset", "sort", "q" }` (snapshots only) |
| `GET` | `/api/v1/symbols/{symbol}` | — | `{ "symbol", "name", "sector", "last": SlimLast \| null }` |
| `GET` | `/api/v1/symbols/{symbol}/snapshots` | `?limit=60` | `{ "points": [{ "ts", "price", "change_pct" }] }` |
| `GET` | `/api/v1/symbols/{symbol}/disclosures` | `?limit=20` | `{ "items": [{ "id", "external_id", "title", "category", "url", "published_at", "company_name", "pdf_url", "brief", "brief_status" }] }` |

`SlimLast` (v1 UI): `price`, `change`, `change_pct`, `volume`, `ts`. Do not render OHLC / market_cap as a quote board even if present in DB.

### Health (ops-gated)

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/api/v1/health` | session required | `{ "status": "ok"\|"degraded", "db_ok", "started_at", "last_snapshot_at"?, "poller"? }` |

Proxy or re-expose existing poller `/health` — do not invent a second source of truth. Not anonymously public by default.

### Conventions
- Symbol normalize: uppercase, same regex as bot (`SYMBOL_RE`).
- NFA is **UI-only** (`disclaimer()` chrome) — not required on JSON bodies.
- No WebSocket in v1; pages refresh on navigation only (no short-poll quote loop).

---

## 4. Auth recommendation

**Canonical ADR:** [001-dash-auth.md](../adr/001-dash-auth.md) (WS-023).

| Phase | Approach |
|---|---|
| **v1 local/demo** | Env allowlist `DASH_DEMO_TELEGRAM_IDS` + `DASH_DEMO_AUTH=1` + non-empty `DASH_SESSION_SECRET`. `POST /auth/demo` mints a **signed HttpOnly session** bound to `users.id`. CSRF on mutating routes. |
| **Banned** | Shared secret + client-supplied `telegram_id` / `X-Telegram-Id` as sole auth; secret-in-cookie; open-network demo without allowlist. |
| **Future** | [Telegram Login Widget](https://core.telegram.org/widgets/login): verify `hash` with bot token; upsert `users.telegram_id`; same session shape. Drop demo endpoint in production. Stub must not accept forged hashes. |

Do not introduce email/password, OAuth providers, or multi-tenant orgs in v1. Dashboard identity = Telegram user row. Dashboard reads Postgres only.

---

## 5. Explicitly out of scope (per page)

| Page | Out of scope |
|---|---|
| `/login` | Marketing site, waitlist, payments, multi-provider SSO |
| `/market` | Screener, OHLC board, multi-sort UI, live ticks, portfolio actions |
| `/watchlist` | Portfolio quantities, cost basis, P&L, sector allocation |
| `/alerts` | Complex boolean rules, trailing stops, backtests, quiet hours UI |
| `/alerts/history` | Analytics funnels, export-to-tax, “would have made” sims |
| `/symbols/[symbol]` | Full TA charts, order book, screener peers, news scrape beyond CSE disclosures |
| `/health` | Deploy controls, secret editing, CSE rate-limit knobs |

Global bans (every page): tax reports, screener, payments, native-app CTAs, competitor data.

---

## 6. Bot command → UI action map

| Bot command | UI equivalent |
|---|---|
| `/start` | `/login` + post-auth landing; copy mirrors bot explainer + NFA |
| `/watch SYMBOL` | Watchlist → Add symbol (`POST /watchlist`) |
| `/unwatch SYMBOL` | Watchlist row → Unwatch (`DELETE /watchlist/{symbol}`) |
| `/alert SYMBOL above PRICE` | Alerts → New · type `price_above` · threshold |
| `/alert SYMBOL below PRICE` | Alerts → New · type `price_below` · threshold |
| `/alert SYMBOL move PERCENT` | Alerts → New · type `daily_move` · threshold |
| `/alert SYMBOL disclosure` | Alerts → New · type `disclosure` · no threshold |
| `/cancel ALERT_ID` | Alerts row → Cancel (`DELETE /alerts/{id}`) |
| `/myalerts` | `/alerts` list |
| `/mywatchlist` | `/watchlist` list |
| *(push on fire)* | Telegram only; History is read-only audit of `alert_log` |

Parity rule: any mutation available in the UI must use the same storage
semantics as the bot for watchlist/alerts **via Postgres** (upsert known
`stocks` rows, deactivate rules on unwatch, unique active rule constraints).
Never call cse.lk from `web/` — symbol validation is against known `stocks` /
poller data (404 if unknown).

---

## Implementation notes (non-binding)

1. Prefer a thin FastAPI/Starlette (or Next Route Handlers wrapping `chime.storage`) — reuse Postgres schema; no parallel tables.
2. First ship: read-only watchlist + auth demo → then alert CRUD → symbol detail → history → health.
3. Mobile-first list UIs; brand-readable first viewport on `/login` and empty states (quality bar #8).
