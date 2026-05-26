"""
Idempotent database setup (extension, vector tables, Chinook DDL).
Used by FastAPI startup and `python scripts/init_db.py`.
"""
from sqlalchemy import text

from db.connection import sync_engine

INIT_SQL = """
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
"""

CHINOOK_DDL = """
CREATE TABLE IF NOT EXISTS "Artist" (
    "ArtistId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(120)
);

CREATE TABLE IF NOT EXISTS "Album" (
    "AlbumId" SERIAL PRIMARY KEY,
    "Title" VARCHAR(160) NOT NULL,
    "ArtistId" INTEGER NOT NULL REFERENCES "Artist"("ArtistId")
);

CREATE TABLE IF NOT EXISTS "Genre" (
    "GenreId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(120)
);

CREATE TABLE IF NOT EXISTS "MediaType" (
    "MediaTypeId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(120)
);

CREATE TABLE IF NOT EXISTS "Track" (
    "TrackId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(200) NOT NULL,
    "AlbumId" INTEGER REFERENCES "Album"("AlbumId"),
    "MediaTypeId" INTEGER NOT NULL REFERENCES "MediaType"("MediaTypeId"),
    "GenreId" INTEGER REFERENCES "Genre"("GenreId"),
    "Composer" VARCHAR(220),
    "Milliseconds" INTEGER NOT NULL,
    "Bytes" INTEGER,
    "UnitPrice" NUMERIC(10,2) NOT NULL DEFAULT 0.99
);

CREATE TABLE IF NOT EXISTS "Employee" (
    "EmployeeId" SERIAL PRIMARY KEY,
    "LastName" VARCHAR(20) NOT NULL,
    "FirstName" VARCHAR(20) NOT NULL,
    "Title" VARCHAR(30),
    "ReportsTo" INTEGER REFERENCES "Employee"("EmployeeId"),
    "BirthDate" TIMESTAMP,
    "HireDate" TIMESTAMP,
    "Address" VARCHAR(70),
    "City" VARCHAR(40),
    "State" VARCHAR(40),
    "Country" VARCHAR(40),
    "PostalCode" VARCHAR(10),
    "Phone" VARCHAR(24),
    "Fax" VARCHAR(24),
    "Email" VARCHAR(60)
);

CREATE TABLE IF NOT EXISTS "Customer" (
    "CustomerId" SERIAL PRIMARY KEY,
    "FirstName" VARCHAR(40) NOT NULL,
    "LastName" VARCHAR(20) NOT NULL,
    "Company" VARCHAR(80),
    "Address" VARCHAR(70),
    "City" VARCHAR(40),
    "State" VARCHAR(40),
    "Country" VARCHAR(40),
    "PostalCode" VARCHAR(10),
    "Phone" VARCHAR(24),
    "Fax" VARCHAR(24),
    "Email" VARCHAR(60) NOT NULL,
    "SupportRepId" INTEGER REFERENCES "Employee"("EmployeeId")
);

CREATE TABLE IF NOT EXISTS "Invoice" (
    "InvoiceId" SERIAL PRIMARY KEY,
    "CustomerId" INTEGER NOT NULL REFERENCES "Customer"("CustomerId"),
    "InvoiceDate" TIMESTAMP NOT NULL,
    "BillingAddress" VARCHAR(70),
    "BillingCity" VARCHAR(40),
    "BillingState" VARCHAR(40),
    "BillingCountry" VARCHAR(40),
    "BillingPostalCode" VARCHAR(10),
    "Total" NUMERIC(10,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS "InvoiceLine" (
    "InvoiceLineId" SERIAL PRIMARY KEY,
    "InvoiceId" INTEGER NOT NULL REFERENCES "Invoice"("InvoiceId"),
    "TrackId" INTEGER NOT NULL REFERENCES "Track"("TrackId"),
    "UnitPrice" NUMERIC(10,2) NOT NULL,
    "Quantity" INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS "Playlist" (
    "PlaylistId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(120)
);

CREATE TABLE IF NOT EXISTS "PlaylistTrack" (
    "PlaylistId" INTEGER NOT NULL REFERENCES "Playlist"("PlaylistId"),
    "TrackId" INTEGER NOT NULL REFERENCES "Track"("TrackId"),
    PRIMARY KEY ("PlaylistId", "TrackId")
);
"""


def seed_chinook_data() -> bool:
    with sync_engine.connect() as conn:
        artist_count = conn.execute(
            text('SELECT COUNT(*) FROM "Artist"')
        ).scalar()

        if artist_count == 0:
            print("⚠ No Chinook data found.")
            print("  Run: python scripts/migrate_chinook.py  (downloads sample data; no extra DB needed)")
            return False
        print(f"◈ Chinook data present ({artist_count} artists).")
        return True


def init_database() -> None:
    """Create pgvector extension, agent tables, and Chinook schema if missing."""
    with sync_engine.connect() as conn:
        conn.execute(text(INIT_SQL))
        conn.commit()
    print("◈ Vector tables initialized.")

    with sync_engine.connect() as conn:
        conn.execute(text(CHINOOK_DDL))
        conn.commit()
    print("◈ Chinook schema initialized.")

    seed_chinook_data()

    # Migration: remove dead success_count column if present from older schema
    with sync_engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE fewshot_examples
            DROP COLUMN IF EXISTS success_count
        """))
        conn.commit()

    print("◈ Database initialized successfully.")
