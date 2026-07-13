-- 010_order_book_imbalance.sql
-- Public CSE POST /orderBook exposes totalBids / totalAsks (side imbalance).

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
    'ask_heavy'
));

-- Latest order-book imbalance snapshot per symbol (poller-written).
CREATE TABLE IF NOT EXISTS order_book_snapshots (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES stocks(symbol),
    total_bids DOUBLE PRECISION NOT NULL,
    total_asks DOUBLE PRECISION NOT NULL,
    best_bid DOUBLE PRECISION,
    best_bid_qty DOUBLE PRECISION,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_order_book_snapshots_symbol_ts
    ON order_book_snapshots (symbol, ts DESC);
