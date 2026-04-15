"""
One-time migration: copy full Chinook data from the 'chinook' database
(created by chinook_postgres.sql) into the 'nexus_sql' database.
Chinook uses lowercase/snake_case; nexus_sql uses PascalCase.
Run order respects FK constraints.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

CHINOOK_URL = "postgresql://nexus:nexus@localhost:5432/chinook"
NEXUS_URL   = os.environ["DATABASE_URL"]

src = create_engine(CHINOOK_URL)
dst = create_engine(NEXUS_URL)

TABLES = [
    # (src_table, dst_table, [(src_col, dst_col), ...])
    ("genre",         '"Genre"',        [("genre_id","GenreId"), ("name","Name")]),
    ("media_type",    '"MediaType"',     [("media_type_id","MediaTypeId"), ("name","Name")]),
    ("artist",        '"Artist"',        [("artist_id","ArtistId"), ("name","Name")]),
    ("album",         '"Album"',         [("album_id","AlbumId"), ("title","Title"), ("artist_id","ArtistId")]),
    ("employee",      '"Employee"',      [
        ("employee_id","EmployeeId"), ("last_name","LastName"), ("first_name","FirstName"),
        ("title","Title"), ("reports_to","ReportsTo"), ("birth_date","BirthDate"),
        ("hire_date","HireDate"), ("address","Address"), ("city","City"),
        ("state","State"), ("country","Country"), ("postal_code","PostalCode"),
        ("phone","Phone"), ("fax","Fax"), ("email","Email"),
    ]),
    ("customer",      '"Customer"',      [
        ("customer_id","CustomerId"), ("first_name","FirstName"), ("last_name","LastName"),
        ("company","Company"), ("address","Address"), ("city","City"),
        ("state","State"), ("country","Country"), ("postal_code","PostalCode"),
        ("phone","Phone"), ("fax","Fax"), ("email","Email"), ("support_rep_id","SupportRepId"),
    ]),
    ("track",         '"Track"',         [
        ("track_id","TrackId"), ("name","Name"), ("album_id","AlbumId"),
        ("media_type_id","MediaTypeId"), ("genre_id","GenreId"), ("composer","Composer"),
        ("milliseconds","Milliseconds"), ("bytes","Bytes"), ("unit_price","UnitPrice"),
    ]),
    ("invoice",       '"Invoice"',       [
        ("invoice_id","InvoiceId"), ("customer_id","CustomerId"), ("invoice_date","InvoiceDate"),
        ("billing_address","BillingAddress"), ("billing_city","BillingCity"),
        ("billing_state","BillingState"), ("billing_country","BillingCountry"),
        ("billing_postal_code","BillingPostalCode"), ("total","Total"),
    ]),
    ("invoice_line",  '"InvoiceLine"',   [
        ("invoice_line_id","InvoiceLineId"), ("invoice_id","InvoiceId"),
        ("track_id","TrackId"), ("unit_price","UnitPrice"), ("quantity","Quantity"),
    ]),
    ("playlist",      '"Playlist"',      [("playlist_id","PlaylistId"), ("name","Name")]),
    ("playlist_track",'"PlaylistTrack"', [("playlist_id","PlaylistId"), ("track_id","TrackId")]),
]

with src.connect() as s, dst.connect() as d:
    d.execute(text("SET session_replication_role = replica"))
    for src_tbl, dst_tbl, cols in TABLES:
        src_cols = ", ".join(c[0] for c in cols)
        dst_cols = ", ".join(f'"{c[1]}"' for c in cols)
        placeholders = ", ".join(f":{c[0]}" for c in cols)

        rows = s.execute(text(f"SELECT {src_cols} FROM {src_tbl}")).mappings().all()
        if rows:
            d.execute(
                text(f'INSERT INTO {dst_tbl} ({dst_cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'),
                [dict(r) for r in rows]
            )
        print(f"  {dst_tbl}: {len(rows)} rows inserted")

    d.execute(text("SET session_replication_role = DEFAULT"))
    d.commit()

print("\nMigration complete.")
