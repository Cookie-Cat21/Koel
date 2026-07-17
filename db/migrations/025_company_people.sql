-- People (directors / CEOs / key officers) extracted from public annual PDFs.
-- Research visualization only (NFA). Personal net worth is NOT stored —
-- dash sizes people by linked company market cap / equity proxies.

CREATE TABLE IF NOT EXISTS filing_people_extracts (
    id BIGSERIAL PRIMARY KEY,
    disclosure_id BIGINT NOT NULL UNIQUE
        REFERENCES disclosures(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL REFERENCES stocks(symbol),
    people_ok BOOLEAN NOT NULL DEFAULT FALSE,
    extract_ok BOOLEAN NOT NULL DEFAULT FALSE,
    extract_notes JSONB NOT NULL DEFAULT '{}'::jsonb,
    pdf_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS people (
    id BIGSERIAL PRIMARY KEY,
    display_name TEXT NOT NULL,
    name_norm TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_people_name_norm
    ON people (name_norm);

CREATE TABLE IF NOT EXISTS person_company_roles (
    id BIGSERIAL PRIMARY KEY,
    person_id BIGINT NOT NULL
        REFERENCES people(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL REFERENCES stocks(symbol) ON DELETE CASCADE,
    role TEXT NOT NULL
        CHECK (role IN (
            'chairman',
            'deputy_chairman',
            'ceo',
            'managing_director',
            'executive_director',
            'non_executive_director',
            'independent_director',
            'senior_independent_director',
            'cfo',
            'company_secretary',
            'director',
            'key_management'
        )),
    confidence TEXT NOT NULL
        CHECK (confidence IN ('low', 'medium', 'high')),
    evidence_disclosure_id BIGINT
        REFERENCES disclosures(id) ON DELETE SET NULL,
    evidence_page INT,
    evidence_snippet TEXT,
    extract_notes JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (person_id, symbol, role)
);

CREATE INDEX IF NOT EXISTS idx_person_company_roles_symbol
    ON person_company_roles (symbol) WHERE active;
CREATE INDEX IF NOT EXISTS idx_person_company_roles_person
    ON person_company_roles (person_id) WHERE active;
CREATE INDEX IF NOT EXISTS idx_person_company_roles_role
    ON person_company_roles (role) WHERE active;
