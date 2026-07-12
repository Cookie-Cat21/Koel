-- Wave4: lease claimed briefs as ``processing`` so concurrent drainers cannot
-- double-claim after FOR UPDATE ends, and daily-cap accounting can include
-- in-flight rows.

ALTER TABLE disclosure_briefs
    DROP CONSTRAINT IF EXISTS disclosure_briefs_status_check;

ALTER TABLE disclosure_briefs
    ADD CONSTRAINT disclosure_briefs_status_check
    CHECK (status IN ('pending', 'processing', 'ready', 'failed', 'skipped'));
