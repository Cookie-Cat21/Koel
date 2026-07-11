-- E2-C04: durable Telegram-OK guard so restart cannot re-push after mark_alert_sent fail.
ALTER TABLE alert_log
    ADD COLUMN IF NOT EXISTS delivery_attempted_ok BOOLEAN NOT NULL DEFAULT FALSE;

DROP INDEX IF EXISTS idx_alert_log_unsent;
CREATE INDEX IF NOT EXISTS idx_alert_log_unsent
    ON alert_log (fired_at)
    WHERE message_sent = FALSE
      AND dead_lettered = FALSE
      AND delivery_attempted_ok = FALSE;
