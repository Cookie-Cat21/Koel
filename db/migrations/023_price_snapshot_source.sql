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
WITH survivors AS (
    SELECT DISTINCT ON (symbol, ts)
        id AS keep_id,
        symbol,
        ts
    FROM price_snapshots
    ORDER BY symbol, ts, id
),
dupes AS (
    SELECT p.id AS drop_id, s.keep_id
    FROM price_snapshots AS p
    JOIN survivors AS s
      ON s.symbol = p.symbol
     AND s.ts = p.ts
    WHERE p.id <> s.keep_id
)
UPDATE alert_log AS al
SET snapshot_id = d.keep_id
FROM dupes AS d
WHERE al.snapshot_id = d.drop_id;

DELETE FROM price_snapshots AS a
    USING price_snapshots AS b
    WHERE a.symbol = b.symbol
      AND a.ts = b.ts
      AND a.id > b.id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_price_snapshots_symbol_ts_uid
    ON price_snapshots (symbol, ts);

CREATE INDEX IF NOT EXISTS idx_price_snapshots_symbol_source_ts
    ON price_snapshots (symbol, source, ts DESC);
