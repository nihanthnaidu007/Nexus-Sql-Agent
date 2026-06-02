"""
Seed schema embeddings for all 11 Chinook tables.
--skip-if-exists: if schema_embeddings count > 0, exit early.
"""
import sys
import os
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from nixus.utils.embeddings import embed_text
from nixus.db.schema_store import store_schema_embedding, get_schema_count

TABLES = [
    {
        "table_name": "Artist",
        "description": (
            'The "Artist" table stores music artist records. Each artist has a unique ArtistId and a Name. '
            'Linked to Album via ArtistId. Useful for queries about discography size, track counts per artist, '
            'revenue per artist, most popular artists.'
        ),
        "columns": [
            {"name": "ArtistId", "type": "integer", "description": "Unique artist identifier (primary key)", "nullable": False},
            {"name": "Name", "type": "varchar(120)", "description": "Artist name", "nullable": True}
        ],
        "samples": {"ArtistId": [1, 2, 3], "Name": ["AC/DC", "Accept", "Aerosmith"]}
    },
    {
        "table_name": "Album",
        "description": (
            'The "Album" table links artists to their albums. Each album has a unique AlbumId, a Title, '
            'and an ArtistId foreign key back to the Artist table. '
            'Critical bridge table for artist-revenue queries: '
            'Artist → Album → Track → InvoiceLine is the required join path '
            'for any revenue-by-artist calculation. '
            'Also used for album count per artist, track count per album, and discography queries.'
        ),
        "columns": [
            {"name": "AlbumId", "type": "integer", "description": "Unique album identifier (primary key)", "nullable": False},
            {"name": "Title", "type": "varchar(160)", "description": "Album title", "nullable": False},
            {"name": "ArtistId", "type": "integer", "description": "Foreign key to Artist", "nullable": False}
        ],
        "samples": {"AlbumId": [1, 2, 3], "Title": ["For Those About To Rock", "Balls to the Wall", "Restless and Wild"], "ArtistId": [1, 2, 2]}
    },
    {
        "table_name": "Track",
        "description": (
            'The "Track" table stores individual music tracks. Linked to Album, Genre, MediaType. '
            'Contains Milliseconds (duration), Bytes (file size), UnitPrice. Key for queries about '
            'track length, price, genre breakdown, composer analysis.'
        ),
        "columns": [
            {"name": "TrackId", "type": "integer", "description": "Unique track identifier", "nullable": False},
            {"name": "Name", "type": "varchar(200)", "description": "Track name", "nullable": False},
            {"name": "AlbumId", "type": "integer", "description": "Foreign key to Album", "nullable": True},
            {"name": "MediaTypeId", "type": "integer", "description": "Foreign key to MediaType", "nullable": False},
            {"name": "GenreId", "type": "integer", "description": "Foreign key to Genre", "nullable": True},
            {"name": "Composer", "type": "varchar(220)", "description": "Composer name(s)", "nullable": True},
            {"name": "Milliseconds", "type": "integer", "description": "Track duration in milliseconds", "nullable": False},
            {"name": "Bytes", "type": "integer", "description": "File size in bytes", "nullable": True},
            {"name": "UnitPrice", "type": "numeric(10,2)", "description": "Price per track (usually 0.99)", "nullable": False}
        ],
        "samples": {"TrackId": [1, 2, 3], "Name": ["For Those About To Rock", "Balls to the Wall", "Fast As a Shark"], "Milliseconds": [343719, 342562, 230619], "UnitPrice": [0.99, 0.99, 0.99]}
    },
    {
        "table_name": "Genre",
        "description": (
            'The "Genre" table categorizes tracks by music genre. Each Genre has a GenreId and Name. '
            'Linked from Track via GenreId. Used for genre-based analysis, track counts per genre, revenue by genre.'
        ),
        "columns": [
            {"name": "GenreId", "type": "integer", "description": "Unique genre identifier", "nullable": False},
            {"name": "Name", "type": "varchar(120)", "description": "Genre name (Rock, Jazz, Metal, etc.)", "nullable": True}
        ],
        "samples": {"GenreId": [1, 2, 3], "Name": ["Rock", "Jazz", "Metal"]}
    },
    {
        "table_name": "MediaType",
        "description": (
            'The "MediaType" table defines the format of tracks (MPEG audio, AAC, etc.). '
            'Each MediaType has a MediaTypeId and Name. Linked from Track via MediaTypeId.'
        ),
        "columns": [
            {"name": "MediaTypeId", "type": "integer", "description": "Unique media type identifier", "nullable": False},
            {"name": "Name", "type": "varchar(120)", "description": "Media type name (MPEG audio file, AAC, etc.)", "nullable": True}
        ],
        "samples": {"MediaTypeId": [1, 2, 3], "Name": ["MPEG audio file", "Protected AAC audio file", "Protected MPEG-4 video file"]}
    },
    {
        "table_name": "Customer",
        "description": (
            'The "Customer" table stores customer records. Contains personal details: FirstName, LastName, '
            'Company, Address, City, State, Country, PostalCode, Phone, Fax, Email. '
            'Linked to Employee via SupportRepId. Key for customer analysis, geographic distribution, '
            'revenue per customer, top buyers.'
        ),
        "columns": [
            {"name": "CustomerId", "type": "integer", "description": "Unique customer identifier", "nullable": False},
            {"name": "FirstName", "type": "varchar(40)", "description": "Customer first name", "nullable": False},
            {"name": "LastName", "type": "varchar(20)", "description": "Customer last name", "nullable": False},
            {"name": "Company", "type": "varchar(80)", "description": "Customer company", "nullable": True},
            {"name": "Country", "type": "varchar(40)", "description": "Customer country", "nullable": True},
            {"name": "Email", "type": "varchar(60)", "description": "Customer email", "nullable": False},
            {"name": "SupportRepId", "type": "integer", "description": "Foreign key to Employee (support rep)", "nullable": True}
        ],
        "samples": {"CustomerId": [1, 2, 3], "FirstName": ["Luís", "Leonie", "François"], "Country": ["Brazil", "Germany", "Canada"]}
    },
    {
        "table_name": "Invoice",
        "description": (
            'The "Invoice" table records purchase transactions. Each invoice has a unique InvoiceId, '
            'links to a Customer via CustomerId, and has InvoiceDate, billing address fields, and Total amount. '
            'Key for revenue analysis, sales by date, sales by country, total revenue per customer.'
        ),
        "columns": [
            {"name": "InvoiceId", "type": "integer", "description": "Unique invoice identifier", "nullable": False},
            {"name": "CustomerId", "type": "integer", "description": "Foreign key to Customer", "nullable": False},
            {"name": "InvoiceDate", "type": "timestamp", "description": "Date and time of invoice", "nullable": False},
            {"name": "BillingAddress", "type": "varchar(70)", "description": "Billing street address", "nullable": True},
            {"name": "BillingCity", "type": "varchar(40)", "description": "Billing city", "nullable": True},
            {"name": "BillingCountry", "type": "varchar(40)", "description": "Billing country", "nullable": True},
            {"name": "Total", "type": "numeric(10,2)", "description": "Invoice total amount", "nullable": False}
        ],
        "samples": {"InvoiceId": [1, 2, 3], "InvoiceDate": ["2009-01-01", "2009-01-02", "2009-01-03"], "Total": [1.98, 3.96, 5.94]}
    },
    {
        "table_name": "InvoiceLine",
        "description": (
            'The "InvoiceLine" table is the line items of invoices. Links Invoice to Track. '
            'Contains UnitPrice and Quantity. Key for calculating revenue per track, per artist, per album. '
            'Must join with Invoice and Track for most revenue queries.'
        ),
        "columns": [
            {"name": "InvoiceLineId", "type": "integer", "description": "Unique line item identifier", "nullable": False},
            {"name": "InvoiceId", "type": "integer", "description": "Foreign key to Invoice", "nullable": False},
            {"name": "TrackId", "type": "integer", "description": "Foreign key to Track", "nullable": False},
            {"name": "UnitPrice", "type": "numeric(10,2)", "description": "Price at time of purchase", "nullable": False},
            {"name": "Quantity", "type": "integer", "description": "Quantity purchased", "nullable": False}
        ],
        "samples": {"InvoiceLineId": [1, 2, 3], "InvoiceId": [1, 1, 2], "TrackId": [2, 4, 6], "Quantity": [1, 1, 1]}
    },
    {
        "table_name": "Employee",
        "description": (
            'The "Employee" table stores Chinook staff. Contains EmployeeId, LastName, FirstName, Title, '
            'ReportsTo (manager), BirthDate, HireDate, Address, City, State, Country. '
            'Used for org chart queries, sales rep performance, employee tenure analysis.'
        ),
        "columns": [
            {"name": "EmployeeId", "type": "integer", "description": "Unique employee identifier", "nullable": False},
            {"name": "LastName", "type": "varchar(20)", "description": "Employee last name", "nullable": False},
            {"name": "FirstName", "type": "varchar(20)", "description": "Employee first name", "nullable": False},
            {"name": "Title", "type": "varchar(30)", "description": "Job title", "nullable": True},
            {"name": "ReportsTo", "type": "integer", "description": "Manager EmployeeId (self-referential FK)", "nullable": True},
            {"name": "HireDate", "type": "timestamp", "description": "Date employee was hired", "nullable": True}
        ],
        "samples": {"EmployeeId": [1, 2, 3], "FirstName": ["Andrew", "Nancy", "Jane"], "Title": ["General Manager", "Sales Manager", "Sales Support Agent"]}
    },
    {
        "table_name": "Playlist",
        "description": (
            'The "Playlist" table stores named playlists. Each playlist has a PlaylistId and Name. '
            'Linked to tracks via PlaylistTrack. Used for playlist size analysis, most popular playlists.'
        ),
        "columns": [
            {"name": "PlaylistId", "type": "integer", "description": "Unique playlist identifier", "nullable": False},
            {"name": "Name", "type": "varchar(120)", "description": "Playlist name", "nullable": True}
        ],
        "samples": {"PlaylistId": [1, 2, 3], "Name": ["Music", "Movies", "TV Shows"]}
    },
    {
        "table_name": "PlaylistTrack",
        "description": (
            'The "PlaylistTrack" junction table links playlists to tracks (many-to-many). '
            'Contains PlaylistId and TrackId as a composite primary key. '
            'Used to find which tracks are in which playlists and vice versa.'
        ),
        "columns": [
            {"name": "PlaylistId", "type": "integer", "description": "Foreign key to Playlist", "nullable": False},
            {"name": "TrackId", "type": "integer", "description": "Foreign key to Track", "nullable": False}
        ],
        "samples": {"PlaylistId": [1, 1, 5], "TrackId": [1, 2, 3]}
    }
]


async def async_main():
    if "--skip-if-exists" in sys.argv:
        count = await get_schema_count()
        if count > 0:
            print(f"◈ Schema embeddings already seeded ({count} tables). Skipping.")
            return

    print(f"◈ Seeding schema embeddings for {len(TABLES)} tables...")
    for i, table in enumerate(TABLES):
        desc = f"{table['description']} Columns: {', '.join(c['name'] for c in table['columns'])}."
        emb = await embed_text(desc)
        await store_schema_embedding(
            table_name=table["table_name"],
            description=table["description"],
            columns_json=json.dumps(table["columns"]),
            sample_values_json=json.dumps(table["samples"]),
            embedding=emb
        )
        print(f"  [{i+1}/{len(TABLES)}] {table['table_name']} ✓")
    print("◈ Schema embeddings seeded successfully.")


if __name__ == "__main__":
    asyncio.run(async_main())
