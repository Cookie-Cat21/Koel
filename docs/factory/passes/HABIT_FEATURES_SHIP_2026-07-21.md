# Habit features ship — 2026-07-21

Implements the five fence-legal opportunities from
[INTL_STOCK_PRODUCT_RESEARCH.md](../INTL_STOCK_PRODUCT_RESEARCH.md).

## Shipped

| Item | Surface |
|---|---|
| Filing category toggles | Settings + `users.disclosure_category_prefs` + rule eval gate |
| Results-day packaging | `results-day filing:` / `results-day metrics:` triggers; Events page results column |
| Close digest + channel habit | Settings digest toggle; channel preview card (W7 copy from Postgres) |
| Watchlist auto 5% | Settings toggle → `daily_move@5` for all watches; sync on add |
| Activity timeline | `/activity` + `GET /api/v1/activity` |
| Events calendar | `/events` + `GET /api/v1/events` |
| TradingView → Telegram | `POST /api/v1/hooks/tradingview?token=…` (needs `TELEGRAM_BOT_TOKEN` on dash) |
| AI briefs path | Unchanged code path; ops still via `AI_BRIEFS_ENABLE.md` (local-fill exists) |

## Migration

`db/migrations/034_habit_prefs_webhook.sql`

## Verify

- Unit: `tests/test_filing_categories.py` (pytest `--no-cov`)
- Loop: `scripts/habit_features_loop.py` → **50/50 PASS**
  (`HABIT_FEATURES_LOOP_2026-07-21.md`)
- Stills: `/opt/cursor/artifacts/ui-stills/09-habit-*.png`

## Ops notes

- AI briefs stay default-off until key soak.
- Public channel posts need `TELEGRAM_PUBLIC_CHANNEL_ID` on the poller.
- TV webhook needs `TELEGRAM_BOT_TOKEN` in the Next.js process env.
