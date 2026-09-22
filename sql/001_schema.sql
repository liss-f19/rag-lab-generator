-- Schema for rag-lab-generator. Applied automatically by the pgvector container on first start.
-- Re-apply manually: psql "$DATABASE_URL" -f sql/001_schema.sql (all statements are idempotent).

CREATE EXTENSION IF NOT EXISTS vector;

-- One row per ingested source document (lab, lecture, course info, external pdf).
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    course      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    lab_id      TEXT,
    title       TEXT NOT NULL,
    source_url  TEXT,
    lang        TEXT NOT NULL DEFAULT 'en',
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Chunks are strategy-scoped: the same document chunked by N strategies yields N disjoint sets.
CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    lab_id      TEXT,
    course      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    strategy    TEXT NOT NULL,
    idx         INTEGER NOT NULL,
    parent_id   TEXT,
    section_id  TEXT,
    text        TEXT NOT NULL,
    char_count  INTEGER NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    tsv         TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_strategy_idx ON chunks(strategy);
CREATE INDEX IF NOT EXISTS chunks_lab_idx ON chunks(lab_id);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING GIN(tsv);

-- Embeddings are embedder-scoped; the column is untyped so embedders of different dims coexist.
-- Corpus is small, sequential cosine scan is acceptable; add a per-embedder HNSW index if needed.
CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id    TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    embedder    TEXT NOT NULL,
    dim         INTEGER NOT NULL,
    embedding   VECTOR NOT NULL,
    PRIMARY KEY (chunk_id, embedder)
);
CREATE INDEX IF NOT EXISTS embeddings_embedder_idx ON embeddings(embedder);

-- Knowledge graph for GraphRAG: nodes point at chunks, edges connect nodes.
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    label       TEXT NOT NULL,
    course      TEXT,
    lab_id      TEXT,
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    properties  JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS nodes_kind_idx ON nodes(kind);
CREATE INDEX IF NOT EXISTS nodes_label_idx ON nodes(lower(label));

CREATE TABLE IF NOT EXISTS node_chunks (
    node_id     TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    chunk_id    TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    PRIMARY KEY (node_id, chunk_id)
);

CREATE TABLE IF NOT EXISTS edges (
    src         TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    dst         TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    weight      REAL NOT NULL DEFAULT 1.0,
    properties  JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (src, dst, kind)
);
CREATE INDEX IF NOT EXISTS edges_dst_idx ON edges(dst);

-- Evaluation runs: one row per (rag, chunker, searcher, embedder) configuration run.
-- Generated node descriptions. No FK on purpose: graph-build recreates nodes under the same
-- ids and the text must survive; source_hash tells graph-describe whether a node changed.
CREATE TABLE IF NOT EXISTS node_descriptions (
    node_id      TEXT PRIMARY KEY,
    text         TEXT NOT NULL,
    source_hash  TEXT NOT NULL,
    model        TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    config      JSONB NOT NULL,
    metrics     JSONB NOT NULL
);
