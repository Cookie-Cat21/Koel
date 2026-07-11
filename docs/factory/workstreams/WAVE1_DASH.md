# WAVE1_DASH — Thin web dashboard workstreams (WS-021…WS-040)

**Lane:** DASH (`web/`, dash API surface)  
**Fence:** [COMMIT_FACTORY.md](../COMMIT_FACTORY.md) §7 + [CLAUDE.md](../../CLAUDE.md)  
**Stack:** Next.js + Tailwind + shadcn/ui (MIT/free only; log in `THIRD_PARTY.md`)  
**Out of scope:** portfolio / P&L, tax, screener, TA charts, payments, native app  

## Theme summary

Wave 1 DASH plans a thin management surface—not a trading terminal—so operators can mirror Telegram watchlist/alert CRUD, inspect fire history and symbol price+disclosures, and see poller health, all backed by a documented Postgres-derived JSON API, a pragmatic shared-secret + `telegram_id` auth stub (Telegram Login Widget deferred), mobile-first IA with mandatory NFA chrome and deliberate empty states, and quality gates that keep the dashboard secondary to push alerts.

---

## Locked product decisions (this wave)

| Topic | Decision |
|---|---|
| **Auth (v1)** | **Shared secret** (`DASH_API_SECRET` / `Authorization: Bearer …`) + explicit `telegram_id` (or internal `user_id`) for scoping. Local default: secret from `.env`, single-user picker. **Not** open-to-network. Telegram Login Widget = stub UI + contract only until CORE exposes a verified identity path. |
| **Why not open local-only** | Accidental deploy would expose every user's rules/fires. Secret gate is one env var and matches ops health secrecy. |
| **Why not full Telegram Login first** | Needs bot domain allowlist, HTTPS callback, and identity binding work; delays watchlist UI. Stub keeps the door open without blocking Pass 1. |
| **API host** | Next.js Route Handlers under `web/app/api/*` reading Postgres via `DATABASE_URL` (same schema as Stage A). No separate FastAPI service in v1. |
| **Data source** | Postgres only (poller writes). Dashboard does **not** call cse.lk. |

---

## IA / sitemap (target)

```
/                     → redirect to /watchlist
/watchlist            → user's watched symbols + last price
/alerts               → active alert rules (CRUD)
/alerts/fires         → fire history (alert_log)
/symbols/[symbol]     → last price, sparkline (snapshots), disclosures
/health               → ops: DB + last poll (proxy/mirror of Python /health)
/login                → enter shared secret (+ optional telegram_id)
```

Nav (desktop + mobile bottom or drawer): Watchlist · Alerts · Fires · Health. Symbol pages linked from watchlist rows. No marketing landing in v1.

---

## API contract (from Postgres)

All routes require `Authorization: Bearer <DASH_API_SECRET>` unless noted. Scope with `X-Telegram-Id: <int>` or `?telegram_id=` (must resolve to `users.id`).

| Method | Path | Reads / writes | Shape (sketch) |
|---|---|---|---|
| `GET` | `/api/me` | `users` | `{ user_id, telegram_id, created_at }` |
| `GET` | `/api/watchlist` | `watchlist_items` ⨝ latest `price_snapshots` | `{ items: [{ symbol, name?, price, change_pct, ts }] }` |
| `POST` | `/api/watchlist` | insert `watchlist_items` (+ ensure `stocks`) | body `{ symbol }` → 201 / 409 |
| `DELETE` | `/api/watchlist/[symbol]` | delete row | 204 / 404 |
| `GET` | `/api/alerts` | `alert_rules` where scoped user | `{ rules: [{ id, symbol, type, threshold, active, armed, created_at }] }` |
| `POST` | `/api/alerts` | insert rule (same types as bot) | body `{ symbol, type, threshold? }` |
| `PATCH` | `/api/alerts/[id]` | `active` toggle / soft-cancel | body `{ active: false }` |
| `GET` | `/api/alerts/fires` | `alert_log` ⨝ rules | `{ fires: [{ id, rule_id, symbol, type, event_key, fired_at, message_sent, message_text? }] }` |
| `GET` | `/api/symbols/[symbol]` | `stocks` + latest snapshot | `{ symbol, name, sector, last: { price, change, change_pct, volume, ts } }` |
| `GET` | `/api/symbols/[symbol]/snapshots` | `price_snapshots` | `{ points: [{ ts, price, change_pct }] }` (limit/default 1 session) |
| `GET` | `/api/symbols/[symbol]/disclosures` | `disclosures` | `{ items: [{ external_id, title, url, category, published_at }] }` |
| `GET` | `/api/health` | proxy Python health **or** DB ping + `MAX(price_snapshots.ts)` | `{ status, db_ok, last_snapshot_at?, poller?: … }` |

Types for `alert_rules.type`: `price_above` \| `price_below` \| `daily_move` \| `disclosure` (match `001_initial.sql`). NFA string is **UI-only**; API returns raw facts.

---

## Workstreams

### WS-021 — Amend constitution for thin dashboard

| Field | Content |
|---|---|
| **id** | WS-021 |
| **title** | Amend CLAUDE.md / factory fence for unlocked thin dash |
| **why** | Stage A text still says “no web”; factory already unlocks thin dash — docs must agree before code. |
| **acceptance criterion** | CLAUDE.md states allowed dash surfaces (watchlist, alerts, fires, symbol+disclosures, health) and explicit non-goals; COMMIT_FACTORY §7 unchanged in spirit; RESOURCES.md “web phase” retitled from “out of scope” to “DASH lane stack pointers” with Next/Tailwind/shadcn. |
| **commits** | (1) Amend CLAUDE.md dash scope. (2) Update RESOURCES.md web section. |
| **deps** | none |
| **risk** | Scope creep if wording allows “dashboard” without listing forbidden features — keep non-goals verbatim. |

### WS-022 — IA, sitemap, and page inventory

| Field | Content |
|---|---|
| **id** | WS-022 |
| **title** | Lock information architecture and sitemap |
| **why** | Prevents a fake trading-terminal layout; one job per route. |
| **acceptance criterion** | Doc section (this file or `docs/factory/DASH_IA.md`) lists exact routes above, primary nav items, and what each page does **not** show; matches COMMIT_FACTORY bar #8. |
| **commits** | (1) Add `docs/factory/DASH_IA.md` (or expand this wave) with sitemap + wireframe notes. |
| **deps** | WS-021 |
| **risk** | Adding a landing/marketing page “just because” — reject; `/` redirects to watchlist. |

### WS-023 — Auth approach: shared secret + telegram scope

| Field | Content |
|---|---|
| **id** | WS-023 |
| **title** | Specify v1 auth (shared secret; Telegram Login stubbed) |
| **why** | Must choose before API/UI; wrong default (open local-only) is a data leak. |
| **acceptance criterion** | Written auth ADR: Bearer secret required on all `/api/*`; user scope via `telegram_id`; `/login` sets httpOnly cookie holding secret (or session token derived from it); Telegram Login Widget documented as **stub** (disabled button + “coming soon”); rejection of open-network mode. |
| **commits** | (1) `docs/factory/DASH_AUTH.md` ADR. (2) `.env.example` keys `DASH_API_SECRET`, optional `DASH_DEFAULT_TELEGRAM_ID`. |
| **deps** | WS-021 |
| **risk** | Cookie XSS if secret stored in localStorage — mandate httpOnly cookie or server session. |

### WS-024 — Formalize Postgres → JSON API contract

| Field | Content |
|---|---|
| **id** | WS-024 |
| **title** | Freeze dash API contract from Stage A schema |
| **why** | CORE and DASH agents need a single contract; stops ad-hoc SQL in React. |
| **acceptance criterion** | `docs/factory/DASH_API.md` (or OpenAPI YAML) matches tables in `db/migrations/001_initial.sql`; includes error envelope `{ error: { code, message } }`; pagination for fires/snapshots; no cse.lk calls. |
| **commits** | (1) Add API contract doc. (2) Add example JSON fixtures under `docs/sample_responses/dash/`. |
| **deps** | WS-023 |
| **risk** | Diverging from bot semantics (e.g. cancel vs deactivate) — mirror bot/`Storage` behavior. |

### WS-025 — Scaffold `web/` Next.js + Tailwind + shadcn

| Field | Content |
|---|---|
| **id** | WS-025 |
| **title** | Create Next.js app scaffold with Tailwind and shadcn |
| **why** | Empty `web/` ownership for the lane; Pass 1 needs a runnable shell. |
| **acceptance criterion** | `web/` builds (`pnpm`/`npm`); Tailwind configured; shadcn init with ≥1 primitive (Button); `THIRD_PARTY.md` lists Next, Tailwind, shadcn licenses; `.gitignore` covers `web/node_modules`, `.next`. |
| **commits** | (1) Scaffold Next app + Tailwind. (2) Init shadcn + Button. (3) THIRD_PARTY.md entries. |
| **deps** | WS-021 |
| **risk** | Accidental paid/proprietary UI kits — stick to MIT shadcn only. |

### WS-026 — App shell, brand, and design tokens

| Field | Content |
|---|---|
| **id** | WS-026 |
| **title** | App shell with Chime brand-readable chrome |
| **why** | Bar #8: brand-readable first viewport; not a generic admin template. |
| **acceptance criterion** | Shared layout: wordmark “Chime”, primary nav, content region; CSS variables for color/type; first viewport of `/watchlist` reads as Chime management, not a stock terminal; no purple-glow / fake dashboard chrome. |
| **commits** | (1) Root layout + nav. (2) Tokens + typography. |
| **deps** | WS-025, WS-022 |
| **risk** | Over-designing a marketing hero — keep shell utilitarian but branded. |

### WS-027 — Mobile layout system

| Field | Content |
|---|---|
| **id** | WS-027 |
| **title** | Mobile-first layout and navigation |
| **why** | Users will open the thin dash on phones between Telegram pings. |
| **acceptance criterion** | At 375px width: nav usable (bottom bar or drawer), tables become stacked rows, no horizontal page scroll; documented breakpoint rules; smoke screenshot or Playwright viewport assert. |
| **commits** | (1) Responsive nav. (2) List/row primitives for watchlist/alerts. |
| **deps** | WS-026 |
| **risk** | Dense multi-column tables copied from broker UIs — forbid. |

### WS-028 — Compliance NFA chrome on every page

| Field | Content |
|---|---|
| **id** | WS-028 |
| **title** | Not-financial-advice framing on all price surfaces |
| **why** | CLAUDE.md compliance; dash must match bot tone (SEC SL Part V framing). |
| **acceptance criterion** | Shared `<NfaNotice />` on watchlist, alerts, symbol, fires; short footer disclaimer sitewide; no “buy/sell/recommend” copy in UI strings; copy review checklist in DASH_IA or compliance note. |
| **commits** | (1) NfaNotice component + footer. (2) Wire into layout/pages. |
| **deps** | WS-026 |
| **risk** | Disclaimer-only without contextual NFA near prices — require both footer and near price blocks. |

### WS-029 — Empty states system

| Field | Content |
|---|---|
| **id** | WS-029 |
| **title** | Empty states for watchlist, alerts, fires, disclosures |
| **why** | New users (and fresh DB) must understand next action without looking like a broken app. |
| **acceptance criterion** | Distinct empty copy + CTA for: no watchlist → “Add a symbol or /watch in Telegram”; no alerts; no fires yet; symbol with no disclosures; API unauthorized. No blank tables. |
| **commits** | (1) `EmptyState` primitive. (2) Wire four domain empties + auth empty. |
| **deps** | WS-026, WS-022 |
| **risk** | Empty states that push portfolio onboarding — keep CTAs inside fence. |

### WS-030 — API: health + me + read watchlist

| Field | Content |
|---|---|
| **id** | WS-030 |
| **title** | Implement read API: health, me, watchlist |
| **why** | Unblocks read-only Pass 1 UI; proves DB wiring. |
| **acceptance criterion** | Routes match WS-024; 401 without secret; watchlist returns latest snapshot join; health returns `db_ok` and last snapshot time (and optional poller proxy if `HEALTH_URL` set); unit/integration test with test DB or mocked pool. |
| **commits** | (1) DB client helper in `web/`. (2) `/api/health`, `/api/me`. (3) `GET /api/watchlist`. |
| **deps** | WS-024, WS-023, WS-025 |
| **risk** | N+1 queries per symbol — use DISTINCT ON / lateral join for latest snapshot. |

### WS-031 — Watchlist page (read + add/remove)

| Field | Content |
|---|---|
| **id** | WS-031 |
| **title** | Watchlist UI mirroring bot /watch /unwatch |
| **why** | Core allowed surface; primary dash job. |
| **acceptance criterion** | List symbols with last price + %; add symbol form; remove control; empty state from WS-029; NFA visible; mobile OK; mutations hit API and refresh. |
| **commits** | (1) Read-only watchlist page. (2) POST/DELETE wired. (3) Optimistic or revalidate UX. |
| **deps** | WS-030, WS-027, WS-028, WS-029 |
| **risk** | Adding quotes polling from cse.lk in the browser — forbidden; show DB last only + “as of ts”. |

### WS-032 — API: alerts CRUD

| Field | Content |
|---|---|
| **id** | WS-032 |
| **title** | Implement alerts list/create/deactivate API |
| **why** | Parity with bot `/alert` and `/cancel`. |
| **acceptance criterion** | GET/POST/PATCH per contract; unique active constraint surfaces as 409; types validated; deactivate sets `active=false` (same spirit as cancel); tests for validation. |
| **commits** | (1) GET list. (2) POST create. (3) PATCH deactivate. |
| **deps** | WS-030, WS-024 |
| **risk** | Creating rules without ensuring symbol on watchlist — decide explicitly (recommend: auto-watch on alert create, matching helpful bot UX if present; document either way). |

### WS-033 — Alerts page UI

| Field | Content |
|---|---|
| **id** | WS-033 |
| **title** | Alerts management UI |
| **why** | Second primary surface; must stay simple (four rule types only). |
| **acceptance criterion** | Table/list of active rules; create form (symbol, type, threshold); deactivate control; empty state; NFA; no screener-like filters beyond symbol search. |
| **commits** | (1) List UI. (2) Create + deactivate. |
| **deps** | WS-032, WS-027, WS-028, WS-029 |
| **risk** | Building a “strategy builder” — hard-cap to bot-equivalent fields. |

### WS-034 — API + UI: fire history

| Field | Content |
|---|---|
| **id** | WS-034 |
| **title** | Alert fire history from alert_log |
| **why** | Explains what Telegram already sent; debug dup/loss without logs. |
| **acceptance criterion** | `GET /api/alerts/fires` paginated; UI shows fired_at, symbol, type, message_sent, excerpt; link to symbol; empty “no fires yet”; does not resend Telegram from UI in v1. |
| **commits** | (1) Fires API. (2) `/alerts/fires` page. |
| **deps** | WS-032, WS-027, WS-028, WS-029 |
| **risk** | Exposing other users' fires — enforce user scope via rule join. |

### WS-035 — Symbol detail: price + sparkline

| Field | Content |
|---|---|
| **id** | WS-035 |
| **title** | Symbol page last price and snapshot sparkline |
| **why** | Allowed “symbol detail”; sparkline from stored snapshots only (not TA library). |
| **acceptance criterion** | `/symbols/[symbol]` shows last quote fields + simple sparkline from `/snapshots`; 404 unknown symbol; NFA under price; no RSI/MACD/volume profile. |
| **commits** | (1) Symbol + snapshots API. (2) Symbol page + sparkline component (lightweight SVG/css). |
| **deps** | WS-030, WS-028 |
| **risk** | Pulling `ta` or TradingView widgets — reject; snapshots only. |

### WS-036 — Symbol detail: disclosures list

| Field | Content |
|---|---|
| **id** | WS-036 |
| **title** | Symbol disclosures panel |
| **why** | Completes symbol detail; links out to source URLs already stored. |
| **acceptance criterion** | Disclosures API + UI list title, published_at, external link; empty state; no HTML scrape; NFA remains on page. |
| **commits** | (1) Disclosures API. (2) Panel on symbol page. |
| **deps** | WS-035, WS-029 |
| **risk** | Embedding PDFs/competitors' pages — link out only. |

### WS-037 — Ops health page

| Field | Content |
|---|---|
| **id** | WS-037 |
| **title** | Ops health view for poller/DB |
| **why** | Factory-allowed ops surface; complements Python `/health`. |
| **acceptance criterion** | `/health` page shows status, `db_ok`, last snapshot age, optional poller details from proxied health; degraded styling when stale; no secret leakage in client HTML. |
| **commits** | (1) Enrich `/api/health` if needed. (2) Health page UI. |
| **deps** | WS-030, WS-026 |
| **risk** | Turning health into a full metrics product — keep single-page facts only. |

### WS-038 — Login stub + Telegram Login placeholder

| Field | Content |
|---|---|
| **id** | WS-038 |
| **title** | Login page for shared secret; Telegram widget stub |
| **why** | Closes auth UX loop without blocking on Telegram OAuth. |
| **acceptance criterion** | `/login` accepts secret + telegram_id; sets secure cookie; logout clears; Telegram Login button visible but disabled/stub with note; unauthenticated API/UI redirects to `/login`. |
| **commits** | (1) Login form + cookie session. (2) Middleware/guard. (3) Telegram stub UI. |
| **deps** | WS-023, WS-025 |
| **risk** | Shipping a fake “Login with Telegram” that accepts forged hashes — stub must not claim verification. |

### WS-039 — Dash smoke tests and TTFB budget

| Field | Content |
|---|---|
| **id** | WS-039 |
| **title** | Smoke tests and latency budget for dash |
| **why** | COMMIT_FACTORY bar #3/#8 need proof; prevents unbroken UI regressions. |
| **acceptance criterion** | Script or Playwright smoke: login → watchlist → alerts → fires → symbol → health; document TTFB budget (e.g. p95 &lt; 500ms local for GET watchlist on warm DB); CI job or `package.json` script documented for OPS handoff. |
| **commits** | (1) Smoke test script. (2) Budget note in DASH_API or FINAL-adjacent factory doc. |
| **deps** | WS-031, WS-033, WS-034, WS-035, WS-036, WS-037, WS-038 |
| **risk** | Flaky E2E without DB — provide docker-compose/Neon skip path like CORE pytest skips. |

### WS-040 — DASH Pass-1 report template and lane checklist

| Field | Content |
|---|---|
| **id** | WS-040 |
| **title** | Pass report template and DASH convergence checklist |
| **why** | Factory loop needs VERIFY/REPORT artifacts per lane. |
| **acceptance criterion** | `docs/factory/DASH_PASS_TEMPLATE.md` with proof slots (build, smoke, fence check); checklist mapping WS-021…039 → done/deferred; STOP rule restated (2 clean passes). |
| **commits** | (1) Add pass template + checklist. |
| **deps** | WS-022, WS-024, WS-039 |
| **risk** | Checklist inflation beyond thin dash — keep mapped to allowed surfaces only. |

---

## Dependency sketch

```
WS-021 ─┬─ WS-022 ─ WS-026 ─┬─ WS-027 ─┬─ WS-031 … WS-037
        ├─ WS-023 ─ WS-024 ─ WS-030 ─┴─ WS-032 ─┘
        └─ WS-025 ─┘         │
                             ├─ WS-028, WS-029 (cross-cut UI)
                             └─ WS-038
                                    └─ WS-039 ─ WS-040
```

Parallelizable early: WS-022 / WS-023 / WS-025 after WS-021.  
UI CRUD streams (031–037) parallelize once read API + shell exist, with file ownership split by route.

## Explicit non-goals (reject if proposed in DASH commits)

- Portfolio balances, P&L, average cost, tax lots  
- Screener / multi-symbol sort beyond user's watchlist  
- TA indicators, TradingView embeds, full candle charts  
- Payments, subscriptions, teams  
- Scraping csetracker.lk or any non–cse.lk/Postgres source from the dash  

---

*Planning only — no product implementation in this document's commit set beyond docs referenced above.*
