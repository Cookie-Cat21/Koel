-- Issuer registry fields from CSE companyInfoSummery + companyProfile.
-- Dash is Postgres-only; poller/backfill writes here. Not a trading board.

CREATE TABLE IF NOT EXISTS issuer_profiles (
    symbol TEXT PRIMARY KEY REFERENCES stocks (symbol) ON DELETE CASCADE,
    isin TEXT,
    board_type TEXT,
    founded TEXT,
    fin_year_end TEXT,
    quoted_date TEXT,
    website TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    auditors TEXT,
    secretaries TEXT,
    business_summary TEXT,
    beta_aspi DOUBLE PRECISION,
    beta_sl20 DOUBLE PRECISION,
    beta_period TEXT,
    market_cap_pct DOUBLE PRECISION,
    shares_issued DOUBLE PRECISION,
    par_value DOUBLE PRECISION,
    foreign_pct DOUBLE PRECISION,
    logo_path TEXT,
    top_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_issuer_profiles_updated_at
    ON issuer_profiles (updated_at DESC);
