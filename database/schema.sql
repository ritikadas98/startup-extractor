-- startup_intel schema (Postgres / Supabase). Source of truth for all tables.
-- Apply with: python -m cli.main init-db  (idempotent)

CREATE EXTENSION IF NOT EXISTS vector;

-- Deduplication anchor
CREATE TABLE IF NOT EXISTS articles (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url               TEXT NOT NULL UNIQUE,
    url_hash          TEXT NOT NULL UNIQUE,          -- SHA-256 of normalized URL
    title             TEXT,
    source            TEXT NOT NULL,
    published_at      TIMESTAMPTZ,
    article_text      TEXT,
    word_count        INTEGER,
    processing_status TEXT NOT NULL DEFAULT 'pending',  -- pending|fetched|processing|complete|failed|duplicate
    processing_error  TEXT,
    retry_count       INTEGER NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    fts               tsvector GENERATED ALWAYS AS (
                        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(article_text, ''))
                      ) STORED
);
CREATE INDEX IF NOT EXISTS idx_articles_fts ON articles USING gin(fts);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(processing_status);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);

CREATE TABLE IF NOT EXISTS companies (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name              TEXT NOT NULL,
    name_normalized   TEXT NOT NULL UNIQUE,
    website           TEXT,
    careers_url       TEXT,
    linkedin_url      TEXT,
    hq_city           TEXT,
    industry          TEXT,
    business_model    TEXT,
    employee_estimate TEXT,
    north_star_metric TEXT,
    job_target_score  REAL DEFAULT 0.0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS funding_rounds (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id       BIGINT NOT NULL REFERENCES companies(id),
    article_id       BIGINT NOT NULL REFERENCES articles(id),
    amount_usd       REAL,
    amount_raw       TEXT,
    currency         TEXT,
    stage            TEXT,
    announced_date   DATE,
    total_raised_usd REAL,
    UNIQUE(company_id, article_id)
);

CREATE TABLE IF NOT EXISTS investors (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            TEXT NOT NULL,
    name_normalized TEXT NOT NULL UNIQUE,
    investor_type   TEXT
);

CREATE TABLE IF NOT EXISTS round_investors (
    round_id    BIGINT NOT NULL REFERENCES funding_rounds(id),
    investor_id BIGINT NOT NULL REFERENCES investors(id),
    is_lead     BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (round_id, investor_id)
);

CREATE TABLE IF NOT EXISTS founders (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         TEXT NOT NULL,
    linkedin_url TEXT,
    role         TEXT
);

CREATE TABLE IF NOT EXISTS company_founders (
    company_id BIGINT NOT NULL REFERENCES companies(id),
    founder_id BIGINT NOT NULL REFERENCES founders(id),
    PRIMARY KEY (company_id, founder_id)
);

-- All 8 Gemini analysis layers stored here
CREATE TABLE IF NOT EXISTS analysis_results (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    article_id         BIGINT NOT NULL REFERENCES articles(id),
    company_id         BIGINT REFERENCES companies(id),
    layer_number       INTEGER NOT NULL CHECK (layer_number BETWEEN 1 AND 8),
    layer_name         TEXT NOT NULL,
    model_used         TEXT NOT NULL,
    result_json        JSONB NOT NULL,
    tokens_input       INTEGER,
    tokens_output      INTEGER,
    cache_read_tokens  INTEGER DEFAULT 0,
    cost_usd           REAL,
    processing_time_ms INTEGER,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    fts                tsvector GENERATED ALWAYS AS (to_tsvector('english', result_json::text)) STORED,
    UNIQUE(article_id, layer_number)                  -- safe to retry
);
CREATE INDEX IF NOT EXISTS idx_analysis_fts ON analysis_results USING gin(fts);
CREATE INDEX IF NOT EXISTS idx_analysis_company ON analysis_results(company_id);

-- Semantic search vectors (one per article/layer content kind)
CREATE TABLE IF NOT EXISTS embeddings (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    article_id   BIGINT NOT NULL REFERENCES articles(id),
    layer_number INTEGER,
    content_kind TEXT NOT NULL,                       -- 'article' | 'analysis'
    embedding    vector(768) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(article_id, layer_number, content_kind)
);
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw ON embeddings
    USING hnsw (embedding vector_cosine_ops);

-- Knowledge graph edges
CREATE TABLE IF NOT EXISTS company_relationships (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_a_id      BIGINT NOT NULL REFERENCES companies(id),
    company_b_id      BIGINT NOT NULL REFERENCES companies(id),
    relationship_type TEXT NOT NULL,                  -- same_investor|competitor|same_business_model|same_market|same_stage_quarter
    confidence        REAL DEFAULT 1.0,
    evidence          TEXT,
    detected_by       TEXT NOT NULL,                  -- 'rule' | 'ai'
    UNIQUE(company_a_id, company_b_id, relationship_type)
);

CREATE TABLE IF NOT EXISTS reports (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_type     TEXT NOT NULL,
    report_date     DATE NOT NULL,
    file_path       TEXT NOT NULL,
    content_md      TEXT,
    articles_count  INTEGER,
    companies_count INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(report_type, report_date)
);

-- Pipeline control switches (read by CLI commands locally AND by the daily
-- GitHub Actions run — one switch controls both).
CREATE TABLE IF NOT EXISTS pipeline_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO pipeline_settings (key, value) VALUES
    ('pipeline_enabled', 'true'),        -- master switch: scrape + fetch + analyze
    ('analysis_enabled', 'true'),        -- AI spend only; scraping stays on (cheap)
    ('job_mode',         'true'),        -- Phase E: layer-7/roles features
    ('monthly_budget_usd', '25')         -- analyze refuses to start past this
ON CONFLICT (key) DO NOTHING;

-- Story-level dedup: same funding event covered by several outlets. The first
-- deep-analyzed article is canonical; later copies get status 'duplicate'.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS duplicate_of BIGINT REFERENCES articles(id);
CREATE INDEX IF NOT EXISTS idx_articles_duplicate_of ON articles(duplicate_of);

-- Phase E: live job openings per company (roles finder)
CREATE TABLE IF NOT EXISTS job_roles (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id  BIGINT NOT NULL REFERENCES companies(id),
    title       TEXT NOT NULL,
    location    TEXT,
    department  TEXT,
    url         TEXT,
    source_kind TEXT NOT NULL,                 -- greenhouse|lever|ashby|page
    first_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (company_id, title, location)
);
