-- 022_hybrid_daily_bars.sql
-- Yahoo (long history) + CSE (recent truth) spliced panel for ML research.
-- Does NOT replace daily_bars (CSE-only product spine). Flag-gated ingest.
-- Yahoo ToS: internal training use only — not a dash redistribution feed.

CREATE TABLE IF NOT EXISTS hybrid_daily_bars (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES stocks(symbol) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    open DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    -- cse | yahoo
    source TEXT NOT NULL CHECK (source IN ('cse', 'yahoo')),
    yahoo_ticker TEXT,
    bar_ts TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_hybrid_daily_bars_symbol_date
    ON hybrid_daily_bars (symbol, trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_hybrid_daily_bars_source
    ON hybrid_daily_bars (source);

CREATE INDEX IF NOT EXISTS idx_hybrid_daily_bars_trade_date
    ON hybrid_daily_bars (trade_date DESC);
