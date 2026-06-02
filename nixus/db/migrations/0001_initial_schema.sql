-- 0001 — initial schema baseline. Represents the application schema as of
-- Phase 1.2. Idempotent; safe to apply to an existing database.
--
-- Scope: APPLICATION tables only (schema_embeddings, fewshot_examples,
-- query_cache) and the pgvector extension they require. LangGraph's checkpointer
-- tables (checkpoints, checkpoint_writes, checkpoint_blobs, checkpoint_migrations)
-- are owned by AsyncPostgresSaver.setup() and are intentionally NOT defined here.
-- Chinook sample-data tables are seeded separately (retired in Phase 2.4) and are
-- likewise not part of this migration.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS schema_embeddings (
    id SERIAL PRIMARY KEY,
    table_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    columns_json TEXT NOT NULL,
    sample_values_json TEXT,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS schema_emb_idx ON schema_embeddings
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS fewshot_examples (
    id SERIAL PRIMARY KEY,
    natural_language TEXT NOT NULL,
    sql_query TEXT NOT NULL,
    tables_used TEXT[],
    query_type TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    auto_learned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS fewshot_emb_idx ON fewshot_examples
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS query_cache (
    id SERIAL PRIMARY KEY,
    user_query TEXT NOT NULL,
    query_embedding vector(1536) NOT NULL,
    generated_sql TEXT NOT NULL,
    result_preview_json TEXT,
    row_count INTEGER,
    execution_time_ms FLOAT,
    chart_type TEXT,
    explanation TEXT,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cache_emb_idx ON query_cache
    USING hnsw (query_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Legacy cleanup carried over from the imperative init: older databases had a
-- dead `success_count` column on fewshot_examples. Idempotent no-op on a fresh
-- database (the column is never created above) and on the current database
-- (already dropped).
ALTER TABLE fewshot_examples DROP COLUMN IF EXISTS success_count;
