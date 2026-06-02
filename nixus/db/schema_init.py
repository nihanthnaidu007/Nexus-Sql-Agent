"""
Idempotent database setup. The APPLICATION schema (pgvector extension + vector
tables) is now owned by the numbered SQL migrations under
``nixus/db/migrations/`` and applied by the migration runner. This module drives
the runner for schema, then ensures the Chinook sample schema + data.
Used by FastAPI startup and `python scripts/init_db.py`.
"""
from sqlalchemy import text

from nixus.db.connection import sync_engine
from nixus.db.migrations.runner import apply_migrations_sync

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
    """Apply application-schema migrations, then ensure Chinook sample schema + data."""
    applied = apply_migrations_sync()
    print(f"◈ Migrations applied: {applied if applied else 'none (already up to date)'}")

    with sync_engine.connect() as conn:
        conn.execute(text(CHINOOK_DDL))
        conn.commit()
    print("◈ Chinook schema initialized.")

    seed_chinook_data()

    print("◈ Database initialized successfully.")
