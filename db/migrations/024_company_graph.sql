-- Company relationship + equity (net-worth proxy) graph from public annual PDFs.
-- Research/visualization only (NFA). App-gated via COMPANY_GRAPH_ENABLED.

CREATE TABLE IF NOT EXISTS filing_graph_extracts (
    id BIGSERIAL PRIMARY KEY,
    disclosure_id BIGINT NOT NULL UNIQUE
        REFERENCES disclosures(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL REFERENCES stocks(symbol),
    kind TEXT NOT NULL
        CHECK (kind IN ('quarterly', 'annual', 'unknown')),
    fiscal_period_end DATE,
    entity TEXT NOT NULL DEFAULT 'unknown'
        CHECK (entity IN ('group', 'company', 'unknown')),
    scale TEXT NOT NULL DEFAULT 'unknown'
        CHECK (scale IN ('units', 'thousands', 'millions', 'unknown')),
    currency TEXT NOT NULL DEFAULT 'LKR',
    equity DOUBLE PRECISION,
    equity_label TEXT,
    equity_ok BOOLEAN NOT NULL DEFAULT FALSE,
    relations_ok BOOLEAN NOT NULL DEFAULT FALSE,
    extract_ok BOOLEAN NOT NULL DEFAULT FALSE,
    extract_notes JSONB NOT NULL DEFAULT '{}'::jsonb,
    pdf_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_filing_graph_extracts_symbol_period
    ON filing_graph_extracts (symbol, kind, fiscal_period_end DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS company_graph_nodes (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT UNIQUE REFERENCES stocks(symbol) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    name_norm TEXT NOT NULL,
    node_kind TEXT NOT NULL
        CHECK (node_kind IN ('listed', 'unlisted')),
    equity DOUBLE PRECISION,
    equity_as_of DATE,
    equity_scale TEXT NOT NULL DEFAULT 'unknown'
        CHECK (equity_scale IN ('units', 'thousands', 'millions', 'unknown')),
    equity_currency TEXT NOT NULL DEFAULT 'LKR',
    equity_disclosure_id BIGINT
        REFERENCES disclosures(id) ON DELETE SET NULL,
    equity_confidence TEXT NOT NULL DEFAULT 'none'
        CHECK (equity_confidence IN ('none', 'low', 'medium', 'high')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT company_graph_nodes_listed_symbol CHECK (
        (node_kind = 'listed' AND symbol IS NOT NULL)
        OR (node_kind = 'unlisted' AND symbol IS NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_company_graph_nodes_name_norm
    ON company_graph_nodes (name_norm);

CREATE TABLE IF NOT EXISTS company_graph_edges (
    id BIGSERIAL PRIMARY KEY,
    src_node_id BIGINT NOT NULL
        REFERENCES company_graph_nodes(id) ON DELETE CASCADE,
    dst_node_id BIGINT NOT NULL
        REFERENCES company_graph_nodes(id) ON DELETE CASCADE,
    relation TEXT NOT NULL
        CHECK (relation IN (
            'subsidiary',
            'associate',
            'joint_venture',
            'related_party',
            'group_mention'
        )),
    ownership_pct DOUBLE PRECISION
        CHECK (
            ownership_pct IS NULL
            OR (ownership_pct >= 0 AND ownership_pct <= 100)
        ),
    ownership_pct_confidence TEXT NOT NULL DEFAULT 'none'
        CHECK (ownership_pct_confidence IN ('none', 'low', 'medium', 'high')),
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
    CHECK (src_node_id <> dst_node_id),
    UNIQUE (src_node_id, dst_node_id, relation)
);

CREATE INDEX IF NOT EXISTS idx_company_graph_edges_src
    ON company_graph_edges (src_node_id) WHERE active;
CREATE INDEX IF NOT EXISTS idx_company_graph_edges_dst
    ON company_graph_edges (dst_node_id) WHERE active;
CREATE INDEX IF NOT EXISTS idx_company_graph_edges_confidence
    ON company_graph_edges (confidence) WHERE active;
