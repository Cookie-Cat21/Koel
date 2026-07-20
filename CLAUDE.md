# koel — CSE market dash + Telegram alerts

## What this is

koel is a **Colombo Stock Exchange dashboard** for browsing symbols, watching
what you care about, and managing alert rules — with **Telegram push** as the
differentiator on top (the cherry). When a price crosses a threshold, a daily
% move fires, or a disclosure lands, koel pings Telegram even if the browser
is closed.

CSE Tracker Pro and friends cover portfolio / screener / charts well, but their
price alerts are still browser-open-only. koel’s wedge is real push. The web
app is the daily surface; Telegram is how you hear the market when you’re away.

**Deferred (not yet — do not build these yet):**
- Portfolio quantities / cost basis / P&L tracking
- Tax reports
- Heavy multi-filter stock screener / trading terminal
- Full technical analysis chart suites
- Native mobile app
- Payment integration

**Web dashboard (primary surface):**
Overview home, market browse, watchlist, alerts + fire history, symbol detail
(last price, sparkline, disclosures), and poller health. Stack: Next.js +
Tailwind + shadcn/ui. See `docs/factory/DASH_IA.md`,
`docs/factory/DASH_CAKE_CHERRY.md`, `docs/factory/KOEL_MASTER_PLAN.md`
(maximum fence-legal roadmap), and `docs/factory/COMMIT_FACTORY.md`.

**Signal Board (phased unlock — research scores, not tips):**
Ranked **research scores** from CSE path / filings / sectors with explainable
reasons and optional forecast overlays. Always NFA; never “best to invest” /
buy-sell language. Path history: ~1y daily via `companyChartDataByStock`
(`docs/experiments/CSE_PATH_HISTORY_PROBE.md`). Third-party macros deferred
(`docs/THIRD_PARTY_DATA.md`).

**Telegram (cherry on top):**
`/watch`, `/alert`, `/myalerts`, and fire pushes. Same Postgres truth as the
dash. If a feature doesn’t help “see the market in the dash” or “get pinged on
Telegram when a rule fires,” it does not belong yet.

## Context / competitive landscape (for reasoning, not for building yet)

- cse.lk has undocumented but public JSON endpoints used by their own web
  portal (see Data Sources below). No official docs, no published rate limits.
- CSE's own mobile app has notification *category* toggles but no custom
  per-stock price-threshold alerts, and its push only reaches users of that
  specific app.
- CSE Tracker Pro (csetracker.lk) is a comprehensive local competitor
  (portfolio tracker, tax reports, screener, technical analysis) but its own
  price alerts are explicitly browser-open-only — confirmed on their site.
- Precedent: Zerodha (India's largest broker) had the same gap for years and
  shipped "Tijori Alerts" — a standalone WhatsApp-first filing/alert summarizer
  — specifically to close it, even after Kite already had in-app alerts.

koel = denser CSE dash **plus** Tijori-style push. Not a pure Tracker Pro clone,
and not alerts-only chrome anymore.

## Data sources (observed 2026-07-11 — see `docs/endpoint_probe_report.md`)

Base: `https://www.cse.lk/api/`

**Convention:** Most endpoints are **POST-only** (GET → 405). Prefer
`application/x-www-form-urlencoded` for symbol-scoped calls; empty JSON `{}`
works for many market-wide POSTs. Send browser-like `Origin` / `Referer`.

Prices / market:

- `POST /companyInfoSummery` — form `symbol=` (JSON body → 400) — per-symbol
  quote (`reqSymbolInfo`: last price, change, market cap, numeric `id`)
- `POST /tradeSummary` — body `{}` — **best bulk poller source**; one call
  returns all symbols (`reqTradeSummery[]`)
- `POST /marketStatus` — body `{}` — `{status}` open/closed; prefer for poller
  gating with clock fallback (`docs/CSE_EXTERNAL_DOC_COMPARE.md`)
- `POST /dailyMarketSummery` — body `{}` — end-of-day market aggregates
- `POST /allSectors` — body `{}` — sector list/performance
- `POST /snpData` — body `{}` — S&P Sri Lanka 20 (also `POST /aspiData` for ASPI)
- `POST /detailedTrades` — market-wide trade board (not symbol-filtered)

Charts (do **not** rely on `/chartData` for per-stock):

- `POST /chartData` — form `chartId=`+`period=` can 200, but `symbol=` is
  ignored (index-scale series). JSON body → 400.
- Use `POST /companyChartDataByStock` (`stockId=` + `period=`) or
  `POST /daysTrade` (`symbol=`) instead

Announcements / disclosures:

- `POST /approvedAnnouncement` — body `{}` — market-wide feed
  (`approvedAnnouncements[]`; `symbol` often null — match via company name)
- `POST /getAnnouncementByCompany` — form `symbol=` (optional
  `fromDate`/`toDate` as `YYYY-MM-DD`) — **preferred for watchlists**
- Legacy: `POST /announcements` form `symbol=` — older PDF archive shape

These are reverse-engineered, undocumented, and may change or rate-limit
without notice. Build the poller with a clean adapter layer so a broken
endpoint is a one-file fix, not a rewrite. Log every failed call. Do not
scrape HTML; use the JSON endpoints above.

## MVP scope (v1 — this is the whole build)

1. **Poller** — polls price + disclosure data on an interval during market
   hours (09:30–14:30 SLT, weekdays). Normalizes into a clean internal schema.
   Stores every snapshot (this historical data is itself a future asset —
   don't discard it).
2. **Rule engine** — evaluates each new snapshot against active alert rules.
   Rule types for v1:
   - Price crosses above X
   - Price crosses below X
   - Daily % move exceeds X (up or down)
   - New disclosure/announcement published for a watched symbol
3. **Telegram bot** — the only user-facing surface for v1.
   - `/start` — register user, short explainer
   - `/watch SYMBOL` — add to watchlist
   - `/unwatch SYMBOL`
   - `/alert SYMBOL above PRICE` / `/alert SYMBOL below PRICE`
   - `/alert SYMBOL move PERCENT`
   - `/myalerts` — list active alerts
   - `/mywatchlist`
   - Fires a message the moment a rule matches. Message includes symbol,
     what triggered it, current price, and (for disclosures) a link to the
     source.
4. **Storage** — Postgres. Keep it simple; this is not a big-data problem yet.

## Suggested schema (adjust as needed, don't over-design)

- `stocks (symbol, name, sector)`
- `price_snapshots (symbol, price, change, change_pct, volume, ts)`
- `disclosures (symbol, title, url, published_at, seen_at)`
- `users (telegram_id, created_at)`
- `watchlist_items (user_id, symbol)`
- `alert_rules (user_id, symbol, type, threshold, active, created_at)`
- `alert_log (rule_id, fired_at, message_sent)`

## Tech stack

- Python for poller + bot (matches existing scraping experience from prior
  projects — reuse that muscle, don't relearn a new stack for this)
- `python-telegram-bot` for the bot
- Postgres (Supabase is fine if convenient — matches other projects, gives
  free hosting tier)
- Simple cron / scheduled job for the poller (APScheduler or plain cron) —
  no need for Kafka/Flink-scale infra for this volume of data
- Thin dashboard (when built): Next.js + Tailwind + shadcn; API over existing
  Postgres / koel domain — not a second CSE scraper

## Compliance notes (do not skip)

- This is an information tool, not investment advice. Every bot response
  involving a price or recommendation-adjacent phrasing should carry a short
  "not financial advice" framing, matching the tone CSE Tracker Pro uses in
  their disclaimer (SEC Sri Lanka Part V Market Misconduct — sections on not
  inducing dealing in securities, not disseminating insider information).
- Only use publicly available data. Do not scrape csetracker.lk or any other
  competitor's platform — their ToS explicitly forbids it and it isn't
  needed; cse.lk is the direct source.
- Rate-limit the poller politely. This is unofficial infrastructure — don't
  hammer it in a way that gets noticed or blocked.

## Build order

1. Data adapter layer + verify each cse.lk endpoint still works, log real
   sample responses to `docs/sample_responses/` *(done — see probe report)*
2. Postgres schema + migrations
3. Poller loop writing snapshots
4. Rule engine matching snapshots against rules
5. Telegram bot wired to rule engine + Postgres
6. Manual end-to-end test: set an alert, force a condition, confirm push

## Current status

Stage A (adapter, schema, poller, rules, bot, health) is implemented and
hardened through Stage B Pass 4. Tijori-for-CSE multi-wave Phase 1–2 is
largely landed (waves 1–7): market-wide snapshot persist, thin `/market`
browse (`GET /api/v1/symbols`), sectors, disclosure PDF enrich + brief
plumbing (live Gemini still flag/key gated — `AI_BRIEFS_ENABLED=0`
default). Phase 3 scenario AI is not started. See
`docs/factory/passes/TIJORI_WAVE_REPORT.md` and
`docs/factory/TIJORI_CSE_PLAN.md`. Commit Factory planning lives under
`docs/factory/` (100 workstreams). Keep non-goals and compliance intact;
thin dashboard only within the fence above. Ceyfi merge is deferred.
