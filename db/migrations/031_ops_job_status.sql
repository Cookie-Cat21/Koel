-- 031_ops_job_status.sql
-- Last-run status for ops jobs (sector-backfill, etc.) so Health can show
-- the exact failure reason without scraping GitHub Actions logs.

CREATE TABLE IF NOT EXISTS ops_job_status (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('ok', 'notice', 'failed')),
    summary TEXT NOT NULL,
    detail TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ops_job_status_updated_at_idx
    ON ops_job_status (updated_at DESC);
