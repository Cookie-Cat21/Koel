-- E2-C05: delivery lease so unsent drain can release advisory lock during Telegram I/O.
-- claim_unsent_batch uses FOR UPDATE SKIP LOCKED then sets delivery_lease_until;
-- concurrent pollers skip leased rows instead of double-sending.
ALTER TABLE alert_log
    ADD COLUMN IF NOT EXISTS delivery_lease_until TIMESTAMPTZ;

-- Align with E2-C04 when 003 is not yet applied (IF NOT EXISTS is idempotent).
ALTER TABLE alert_log
    ADD COLUMN IF NOT EXISTS delivery_attempted_ok BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_alert_log_delivery_lease
    ON alert_log (delivery_lease_until)
    WHERE message_sent = FALSE
      AND dead_lettered = FALSE
      AND delivery_lease_until IS NOT NULL;
