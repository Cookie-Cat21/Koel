-- 032_alert_types_h1.sql
-- W2: high_52w / low_52w / ma_cross / ref_move alert types + optional ref_price.

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
    'xd_digest',
    'share_split',
    'high_52w',
    'low_52w',
    'ma_cross',
    'ref_move'
));

ALTER TABLE alert_rules
    ADD COLUMN IF NOT EXISTS ref_price DOUBLE PRECISION;

-- Distinct ref_move rules may share the same % threshold with different refs.
DROP INDEX IF EXISTS idx_alert_rules_unique_active;

CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_rules_unique_active
    ON alert_rules (
        user_id,
        symbol,
        type,
        COALESCE(threshold, -1),
        COALESCE(category, ''),
        COALESCE(ref_price, -1)
    )
    WHERE active;
