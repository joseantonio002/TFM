-- Optional: for UUID-like IDs if you later want generated ids
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS news (
    id                text PRIMARY KEY,
    source_url        text NOT NULL,
    airflow_dag_id    text,
    extracted_at      timestamptz NOT NULL,
    airflow_run_id    text,
    connector_id      text,
    connector_name    text,
    source_name       text,
    source_type       text,
    language          varchar(10),
    country           varchar(10),

    -- Your sample shows this as a JSON string: "[\"public_radio\", \"news\"]"
    -- Better options are jsonb or text[].
    source_tags       jsonb,

    content           text,

    -- Flexible sections that may change often
    other             jsonb,
    nlp_pipeline      jsonb,

    created_at        timestamptz NOT NULL DEFAULT now(),

    -- Basic validation
    CONSTRAINT chk_source_tags_is_array
        CHECK (source_tags IS NULL OR jsonb_typeof(source_tags) = 'array'),

    CONSTRAINT chk_other_is_object
        CHECK (other IS NULL OR jsonb_typeof(other) = 'object'),

    CONSTRAINT chk_nlp_pipeline_is_object
        CHECK (nlp_pipeline IS NULL OR jsonb_typeof(nlp_pipeline) = 'object')
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_media_extractions_extracted_at
    ON media_extractions (extracted_at);

CREATE INDEX IF NOT EXISTS idx_media_extractions_connector_id
    ON media_extractions (connector_id);

CREATE INDEX IF NOT EXISTS idx_media_extractions_source_type
    ON media_extractions (source_type);

CREATE INDEX IF NOT EXISTS idx_media_extractions_language
    ON media_extractions (language);

CREATE INDEX IF NOT EXISTS idx_media_extractions_country
    ON media_extractions (country);

CREATE INDEX IF NOT EXISTS idx_media_extractions_source_tags_gin
    ON media_extractions USING gin (source_tags);

CREATE INDEX IF NOT EXISTS idx_media_extractions_other_gin
    ON media_extractions USING gin (other);

CREATE INDEX IF NOT EXISTS idx_media_extractions_nlp_pipeline_gin
    ON media_extractions USING gin (nlp_pipeline);

-- Optional full text search over content (Spanish example)
CREATE INDEX IF NOT EXISTS idx_media_extractions_content_fts
    ON media_extractions
    USING gin (to_tsvector('spanish', coalesce(content, '')));