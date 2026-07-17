-- Tag CSE chart backfill ticks so alert previous_snapshot ignores them.
-- Poller / tradeSummary rows stay source='poller' (default).

ALTER TABLE price_snapshots
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'poller';

ALTER TABLE price_snapshots
    DROP CONSTRAINT IF EXISTS price_snapshots_source_check;
ALTER TABLE price_snapshots
    ADD CONSTRAINT price_snapshots_source_check
    CHECK (source IN ('poller', 'cse_intraday'));

-- Collapse duplicate (symbol, ts) before unique index (keep lowest id).
-- Remount alert_log FKs onto the survivor row first (Neon had live refs).
UPDATE alert_log AS al
SET snapshot_id = keep.id
FROM price_snapshots AS drop_row
JOIN LATERAL (
    SELECT p.id
    FROM price_snapshots AS p
    WHERE p.symbol = drop_row.symbol
      AND p.ts = drop_row.ts
    ORDER BY p.id
    LIMIT 1
) AS keep ON TRUE
WHERE al.snapshot_id = drop_row.id
  AND drop_row.id <> keep.id;

DELETE FROM price_snapshots AS a
    USING price_snapshots AS b
    WHERE a.symbol = b.symbol
      AND a.ts = b.ts
      AND a.id > b.id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_price_snapshots_symbol_ts_uid
    ON price_snapshots (symbol, ts);

CREATE INDEX IF NOT EXISTS idx_price_snapshots_symbol_source_ts
    ON price_snapshots (symbol, source, ts DESC);
