-- EOD digest idempotency: Colombo calendar date of last successful digest send.
-- digest_enabled (012) gates recipients; quiet hours still gate live alerts only.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_digest_on DATE;
