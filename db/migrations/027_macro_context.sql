-- 027_macro_context.sql
-- Tier B macro series (CBSL FX, EIA oil, DCS food, SLTDA tourism, …)
-- + market-regime alert types. Adapters are flag-gated (default off).

ALTER TABLE alert_rules DROP CONSTRAINT IF EXISTS alert_rules_type_check;
ALTER TABLE alert_rules ADD CONSTRAINT alert_rules_type_check CHECK (type IN (
    'price_above',
    'price_below',
    'daily_move',
    'disclosure',
    'volume_spike',
    'volume_up',
    'volume_down',
    'crossing_volume',
    'big_print',
    'gap',
    'buy_in',
    'non_compliance',
    'halt',
    'bid_heavy',
    'ask_heavy',
    'eps_above',
    'eps_below',
    'eps_yoy_above',
    'eps_yoy_below',
    'rev_yoy_above',
    'rev_yoy_below',
    'profit_yoy_above',
    'profit_yoy_below',
    'appetite_band',
    'foreign_flow',
    'book_pressure',
    'usdlkr_move',
    'oil_move'
));

CREATE TABLE IF NOT EXISTS macro_series (
    source TEXT NOT NULL,
    series_id TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT,
    as_of_date DATE,
    attribution TEXT NOT NULL DEFAULT '',
    raw_hash TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source, series_id, ts)
);

CREATE INDEX IF NOT EXISTS idx_macro_series_series_ts
    ON macro_series (series_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_macro_series_as_of
    ON macro_series (as_of_date DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS macro_snapshots_daily (
    trade_date DATE PRIMARY KEY,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
