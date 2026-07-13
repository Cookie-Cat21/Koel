-- 011_filing_metrics.sql
-- Structured financial PDF extract + YoY compare + calc/YoY alert types.
-- Feature-flagged in app code (FINANCIAL_METRICS_ENABLED etc.). Defaults off.

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
    'profit_yoy_below'
));

CREATE TABLE IF NOT EXISTS filing_metrics (
    id BIGSERIAL PRIMARY KEY,
    disclosure_id BIGINT NOT NULL UNIQUE REFERENCES disclosures(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL REFERENCES stocks(symbol),
    kind TEXT NOT NULL
        CHECK (kind IN ('quarterly', 'annual', 'unknown')),
    fiscal_period_end DATE,
    fiscal_quarter SMALLINT
        CHECK (fiscal_quarter IS NULL OR (fiscal_quarter >= 1 AND fiscal_quarter <= 4)),
    entity TEXT NOT NULL DEFAULT 'unknown'
        CHECK (entity IN ('group', 'company', 'unknown')),
    scale TEXT NOT NULL DEFAULT 'unknown'
        CHECK (scale IN ('units', 'thousands', 'millions', 'unknown')),
    currency TEXT NOT NULL DEFAULT 'LKR',
    revenue DOUBLE PRECISION,
    profit DOUBLE PRECISION,
    eps_basic DOUBLE PRECISION,
    eps_diluted DOUBLE PRECISION,
    extract_ok BOOLEAN NOT NULL DEFAULT FALSE,
    extract_notes JSONB NOT NULL DEFAULT '{}'::jsonb,
    pdf_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_filing_metrics_symbol_period
    ON filing_metrics (symbol, kind, fiscal_period_end DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_filing_metrics_symbol_ok_period
    ON filing_metrics (symbol, extract_ok, fiscal_period_end DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS filing_comparisons (
    id BIGSERIAL PRIMARY KEY,
    filing_metrics_id BIGINT NOT NULL UNIQUE
        REFERENCES filing_metrics(id) ON DELETE CASCADE,
    prior_filing_metrics_id BIGINT
        REFERENCES filing_metrics(id) ON DELETE SET NULL,
    match_quality TEXT NOT NULL
        CHECK (match_quality IN (
            'exact_yoy',
            'approx_yoy',
            'missing_prior',
            'scale_mismatch',
            'entity_mismatch',
            'currency_mismatch',
            'skipped'
        )),
    eps_delta DOUBLE PRECISION,
    eps_delta_pct DOUBLE PRECISION,
    revenue_delta DOUBLE PRECISION,
    revenue_delta_pct DOUBLE PRECISION,
    profit_delta DOUBLE PRECISION,
    profit_delta_pct DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_filing_comparisons_prior
    ON filing_comparisons (prior_filing_metrics_id)
    WHERE prior_filing_metrics_id IS NOT NULL;
