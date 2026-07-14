-- Wave 3-5: market index snapshots, dashboard preferences, sessions, and mutes.
-- Quiet-hour bounds are enforced in app code (0–23); no DO-block CHECKs
-- (statement splitter in migrate sanity cannot keep $$ bodies intact).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS index_snapshots (
    code TEXT,
    name TEXT,
    value DOUBLE PRECISION,
    change DOUBLE PRECISION,
    change_pct DOUBLE PRECISION,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_index_snapshots_code_ts
    ON index_snapshots (code, ts DESC);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS digest_enabled BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS quiet_hours_start SMALLINT;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS quiet_hours_end SMALLINT;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS alert_quota_max INT NOT NULL DEFAULT 100;

ALTER TABLE alert_rules
    ADD COLUMN IF NOT EXISTS muted_until TIMESTAMPTZ NULL;

CREATE TABLE IF NOT EXISTS dash_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_agent TEXT,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_dash_sessions_user_id
    ON dash_sessions (user_id);
