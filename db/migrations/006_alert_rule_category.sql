-- Optional disclosure category filter on alert_rules.
-- NULL = any category (backward compatible). Non-null = case-insensitive substring match.

ALTER TABLE alert_rules
    ADD COLUMN IF NOT EXISTS category TEXT NULL;

-- Allow multiple active disclosure rules per symbol when categories differ.
DROP INDEX IF EXISTS idx_alert_rules_unique_active;

CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_rules_unique_active
    ON alert_rules (user_id, symbol, type, COALESCE(threshold, -1), COALESCE(category, ''))
    WHERE active;
