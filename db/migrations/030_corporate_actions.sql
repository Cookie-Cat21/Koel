-- 030_corporate_actions.sql
-- Share split / consolidation / subdivision calendar + share_split alerts.
-- Sources: CSE disclosure text and near-integer session price ratios.
-- daily_bars stay CSE-unadjusted; charts/returns adjust at read time.

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
    'share_split'
));

CREATE TABLE IF NOT EXISTS corporate_actions (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES stocks(symbol),
    disclosure_id BIGINT REFERENCES disclosures(id) ON DELETE SET NULL,
    effective_date DATE NOT NULL,
    kind TEXT NOT NULL,
    ratio_from INTEGER NOT NULL,
    ratio_to INTEGER NOT NULL,
    title TEXT,
    source TEXT NOT NULL DEFAULT 'cse_disclosure',
    raw_hash TEXT,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT corporate_actions_kind_check CHECK (
        kind IN ('split', 'consolidation')
    ),
    CONSTRAINT corporate_actions_ratio_check CHECK (
        ratio_from > 0 AND ratio_to > 0 AND ratio_from <> ratio_to
    )
);

-- One row per linked disclosure.
CREATE UNIQUE INDEX IF NOT EXISTS uq_corporate_actions_disclosure
    ON corporate_actions (disclosure_id)
    WHERE disclosure_id IS NOT NULL;

-- Natural key when no disclosure (price-ratio detect / bar backfill).
CREATE UNIQUE INDEX IF NOT EXISTS uq_corporate_actions_natural
    ON corporate_actions (symbol, effective_date, kind, ratio_from, ratio_to, source)
    WHERE disclosure_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_corporate_actions_symbol_date
    ON corporate_actions (symbol, effective_date DESC);

CREATE INDEX IF NOT EXISTS idx_corporate_actions_effective
    ON corporate_actions (effective_date DESC);
