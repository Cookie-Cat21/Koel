-- Separate counter for Telegram RetryAfter defers so a flood-waited alert is
-- judged against MAX_DEFERRED_ATTEMPTS, not the tighter MAX_SEND_ATTEMPTS
-- shared with ordinary send failures.
ALTER TABLE alert_log
    ADD COLUMN IF NOT EXISTS deferred_attempt_count INT NOT NULL DEFAULT 0;
