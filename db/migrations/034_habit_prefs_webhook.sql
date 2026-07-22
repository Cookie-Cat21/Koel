-- Habit prefs + TradingView inbound webhook token (INTL research P0–P1).
-- watchlist_auto_move_pct: NULL = off; e.g. 5.0 = auto daily_move on all watches.
-- disclosure_category_prefs: empty = all categories; else allow-list of tags.
-- tv_webhook_token: opaque secret for POST /api/v1/hooks/tradingview.

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS watchlist_auto_move_pct double precision,
  ADD COLUMN IF NOT EXISTS disclosure_category_prefs text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS tv_webhook_token text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_tv_webhook_token
  ON users (tv_webhook_token)
  WHERE tv_webhook_token IS NOT NULL;

COMMENT ON COLUMN users.watchlist_auto_move_pct IS
  'When set (e.g. 5), keep active daily_move rules at that %% for every watchlist symbol.';
COMMENT ON COLUMN users.disclosure_category_prefs IS
  'Allow-list of filing tags (results, board, corporate_action, shareholding, other). Empty = unrestricted.';
COMMENT ON COLUMN users.tv_webhook_token IS
  'Secret for inbound TradingView webhook → Telegram fan-out (never the CSE data spine).';
