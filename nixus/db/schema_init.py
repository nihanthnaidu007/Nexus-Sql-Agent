"""
Idempotent database setup, split across the two databases (2.1).

STATE database (NIXUS-owned, READ-WRITE): the application schema (pgvector
extension + vector tables + ``schema_migrations``) is owned by the numbered SQL
migrations under ``nixus/db/migrations/`` and applied here via the migration
runner.

TARGET database (the user's data, READ-ONLY to the app): the Chinook sample
schema + data now live in their OWN database. They are provisioned out-of-band —
``scripts/init-target-db.sql`` (the compose init script on a fresh stack) creates
the database + read-only role, and ``scripts/migrate_chinook.py`` loads the data
through a writable OWNER connection. The app only ever READS the target, so this
module no longer creates Chinook in the state database; it just reports target
Chinook presence (best-effort, read-only) for operator visibility.

Used by FastAPI startup and `python scripts/init_db.py`.
"""
from sqlalchemy import text

from nixus.db.connection import sync_target_engine
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


def report_chinook_presence() -> bool:
    """Best-effort, READ-ONLY check that the TARGET database has Chinook data.

    Never raises: an unset/unreachable target (or the read-only role lacking the
    table) just prints a hint and returns False, so app startup is never coupled
    to target provisioning. The app reads Chinook through the read-only role; it
    must NOT try to create or seed it here.
    """
    if sync_target_engine is None:
        print("⚠ TARGET_DATABASE_URL not set — skipping Chinook (target_db) presence check.")
        return False
    try:
        with sync_target_engine.connect() as conn:
            artist_count = conn.execute(
                text('SELECT COUNT(*) FROM "Artist"')
            ).scalar()
    except Exception as e:
        print(f"⚠ Could not read Chinook from target_db (read-only): {type(e).__name__}.")
        print("  Provision it: scripts/init-target-db.sql (db+role) + python scripts/migrate_chinook.py (data).")
        return False

    if not artist_count:
        print("⚠ Target Chinook tables present but empty.")
        print("  Run: python scripts/migrate_chinook.py  (loads sample data into target_db)")
        return False
    print(f"◈ Chinook present in target_db ({artist_count} artists, read-only).")
    return True


def init_database() -> None:
    """Apply application-schema migrations to STATE db; report target Chinook."""
    applied = apply_migrations_sync()
    print(f"◈ State migrations applied: {applied if applied else 'none (already up to date)'}")

    report_chinook_presence()

    print("◈ Database initialized successfully.")
