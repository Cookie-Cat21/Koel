-- 028_dividend_events.sql
-- CSE-sourced dividend calendar (announce / XD / pay / DPS) + xd_soon / xd_digest alerts.
-- Source is disclosures + briefs — never LOLC (Tier E).

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
    'oil_move',
    'xd_soon',
    'xd_digest'
));

CREATE TABLE IF NOT EXISTS dividend_events (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES stocks(symbol),
    disclosure_id BIGINT REFERENCES disclosures(id) ON DELETE SET NULL,
    d_ann DATE,
    d_xd DATE,
    d_pay DATE,
    dps DOUBLE PRECISION,
    kind TEXT,
    fy TEXT,
    dates_tbd BOOLEAN NOT NULL DEFAULT FALSE,
    title TEXT,
    source TEXT NOT NULL DEFAULT 'cse_disclosure',
    raw_hash TEXT,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Prefer one row per disclosure when linked; else symbol+xd+dps+source.
CREATE UNIQUE INDEX IF NOT EXISTS uq_dividend_events_disclosure
    ON dividend_events (disclosure_id)
    WHERE disclosure_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_dividend_events_natural
    ON dividend_events (symbol, d_xd, dps, source)
    WHERE disclosure_id IS NULL AND d_xd IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_dividend_events_xd
    ON dividend_events (d_xd)
    WHERE d_xd IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_dividend_events_symbol_xd
    ON dividend_events (symbol, d_xd DESC NULLS LAST);
