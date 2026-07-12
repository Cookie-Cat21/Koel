# Chime — useful open-source resources

Starter list of libraries and patterns for the CSE Telegram alerting stack. Prefer well-maintained packages with clear licenses; pin versions in `pyproject.toml` when implementing.

## Telegram bot

| Resource | License | Notes |
|---|---|---|
| [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) | LGPL-3.0 | Official-ish community wrapper; v20+ is async. |
| [PTB examples](https://github.com/python-telegram-bot/python-telegram-bot/tree/master/examples) | LGPL-3.0 | `/start`, conversation handlers, job queue patterns. |
| [PTB wiki — JobQueue / APScheduler](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions-%E2%80%93-JobQueue) | — | Scheduling tips when co-locating bot + poller. |

## Scheduling / retries

| Resource | License | Notes |
|---|---|---|
| [APScheduler](https://github.com/agronholm/apscheduler) | MIT | Cron/interval jobs for market-hours poller (09:30–14:30 Asia/Colombo). |
| [tenacity](https://github.com/jd/tenacity) | Apache-2.0 | Retry with backoff for flaky cse.lk calls; log every failure. |

## Data / validation / HTTP

| Resource | License | Notes |
|---|---|---|
| [pydantic](https://github.com/pydantic/pydantic) | MIT | Internal schemas (`PriceSnapshot`, `Disclosure`, alert rules). |
| [httpx](https://github.com/encode/httpx) | BSD-3-Clause | Async HTTP client for the CSE adapter layer. |
| [psycopg](https://github.com/psycopg/psycopg) (v3) | LGPL-3.0 | Postgres driver; fine with Supabase. |
| [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) | MIT | Optional ORM; keep schema simple for v1. |
| [alembic](https://github.com/sqlalchemy/alembic) | MIT | Migrations when schema evolves. |

## Logging / config

| Resource | License | Notes |
|---|---|---|
| [structlog](https://github.com/hynek/structlog) | MIT / Apache-2.0 | Structured logs for poller failures and alert fires. |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | BSD-3-Clause | Local `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, etc. |

## Crossing-alert / rule-engine patterns

| Resource | License | Notes |
|---|---|---|
| Classic threshold crossing | — | Fire only on **transition** (prev ≤ X and curr > X), not every poll while above. Persist last evaluated price per rule. |
| Daily % move | — | Compare `change_pct` (or `price` vs `previous_close`) to threshold; debounce to once per session/day per rule. |
| Disclosure dedupe | — | Key on `announcementId`; insert into `disclosures` / `alert_log` before send. |
| [ta (Technical Analysis Library)](https://github.com/bukosabino/ta) | MIT | **Not for v1** — listed only so we do not invent chart indicators early. |

## CSE data hygiene

- Adapter boundary: one module for cse.lk HTTP; normalize to Chime schemas (see [`endpoint_probe_report.md`](endpoint_probe_report.md)).
- Samples of live responses: [`sample_responses/`](sample_responses/).
- External checklist compare: [`CSE_EXTERNAL_DOC_COMPARE.md`](CSE_EXTERNAL_DOC_COMPARE.md).
- **Sibling project (not Chime app code):** [`../cse-api-docs/`](../cse-api-docs/) — unofficial CSE API docs + probe harness. Plan: [`CSE_API_DOCS_PROJECT.md`](CSE_API_DOCS_PROJECT.md). Extract: [`../cse-api-docs/EXTRACT.md`](../cse-api-docs/EXTRACT.md).
- Do not scrape competitors (e.g. csetracker.lk). Public cse.lk JSON only.
- Polite rate limits; treat undocumented APIs as unstable.

## Compliance framing

Bot copy involving prices should include a short “not financial advice” disclaimer (SEC Sri Lanka Part V market misconduct framing — informational tool only).

## Thin web dashboard (greenlit — secondary to Telegram)

A minimal management UI is allowed (watchlist, alerts, fire history,
symbol detail, poller health). Telegram remains the primary surface;
push alerts are the product. See [`factory/DASH_IA.md`](factory/DASH_IA.md)
and [`factory/COMMIT_FACTORY.md`](factory/COMMIT_FACTORY.md) §7.

**Stack when building `web/`:** Next.js + Tailwind + [shadcn/ui](https://ui.shadcn.com/)
only. Free/MIT components; log additions in `THIRD_PARTY.md`. Dashboard
reads Postgres / Chime API only — no second cse.lk client from `web/`.

**Still forbidden:** portfolio / P&L, tax reports, stock screener, technical
analysis charts, payments, native app.

Optional component bookmarks (reference only; prefer shadcn primitives).
**Filter before copying:** [factory/DASH_COMPONENT_FILTER.md](factory/DASH_COMPONENT_FILTER.md)
(Tremor Blocks MIT inventory, ACCEPT/REJECT by fence, bookmark license gate).

- HyperUI (MIT patterns — adapt; don’t dual-stack)
- Tremor Blocks / Raw (MIT — cherry-pick; **no** full Planner/Overview import)
- 21st.dev (per-item MIT verify; no dump-all)
- Cult UI free / Watermelon (MIT confirm; skip Pro)
- daisyUI — inspiration only (do not install beside shadcn)
- React Bits — **skip** (Commons Clause ≠ constitution MIT)
- Shadcnblocks Pro — **skip**; free only with clear LICENSE
- Aceternity / marketing carousels / FAQ footers — **skip** for thin dash
