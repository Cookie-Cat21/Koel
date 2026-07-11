-- WS-006: track Telegram send attempts; dead-letter after N failures.
ALTER TABLE alert_log
    ADD COLUMN IF NOT EXISTS attempt_count INT NOT NULL DEFAULT 0;

ALTER TABLE alert_log
    ADD COLUMN IF NOT EXISTS dead_lettered BOOLEAN NOT NULL DEFAULT FALSE;

DROP INDEX IF EXISTS idx_alert_log_unsent;
CREATE INDEX IF NOT EXISTS idx_alert_log_unsent
    ON alert_log (fired_at)
    WHERE message_sent = FALSE AND dead_lettered = FALSE;
