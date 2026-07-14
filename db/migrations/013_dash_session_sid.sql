-- A2: bind dash_sessions rows to the signed session sid (hex from mint).

ALTER TABLE dash_sessions
    ADD COLUMN IF NOT EXISTS sid TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_dash_sessions_sid
    ON dash_sessions (sid);
