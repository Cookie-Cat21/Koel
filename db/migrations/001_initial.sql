-- 001_initial.sql
-- Koel v1 schema

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES stocks(symbol),
    price DOUBLE PRECISION NOT NULL,
    change DOUBLE PRECISION,
    change_pct DOUBLE PRECISION,
    previous_close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    trade_count DOUBLE PRECISION,
    turnover DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    open DOUBLE PRECISION,
    market_cap DOUBLE PRECISION,
    ts TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_price_snapshots_symbol_ts
    ON price_snapshots (symbol, ts DESC);

CREATE TABLE IF NOT EXISTS disclosures (
    id BIGSERIAL PRIMARY KEY,
    external_id TEXT NOT NULL,
    symbol TEXT NOT NULL REFERENCES stocks(symbol),
    title TEXT NOT NULL,
    category TEXT,
    url TEXT NOT NULL,
    company_name TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (external_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_disclosures_symbol_published
    ON disclosures (symbol, published_at DESC);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL REFERENCES stocks(symbol),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL REFERENCES stocks(symbol),
    type TEXT NOT NULL CHECK (type IN (
        'price_above', 'price_below', 'daily_move', 'disclosure'
    )),
    threshold DOUBLE PRECISION,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    armed BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_rules_unique_active
    ON alert_rules (user_id, symbol, type, COALESCE(threshold, -1))
    WHERE active;

CREATE INDEX IF NOT EXISTS idx_alert_rules_symbol_active
    ON alert_rules (symbol) WHERE active;

CREATE TABLE IF NOT EXISTS alert_log (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    snapshot_id BIGINT REFERENCES price_snapshots(id),
    event_key TEXT NOT NULL,
    fired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    message_sent BOOLEAN NOT NULL DEFAULT FALSE,
    message_text TEXT,
    UNIQUE (rule_id, event_key)
);

CREATE INDEX IF NOT EXISTS idx_alert_log_unsent
    ON alert_log (fired_at) WHERE message_sent = FALSE;
