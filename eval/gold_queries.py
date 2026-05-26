"""
Gold query set for NEXUS SQL evaluation harness.

30 queries across 6 categories:
  A01-A05  Simple filter / single-table SELECT
  B01-B05  Aggregation (GROUP BY)
  C01-C05  Single join
  D01-D05  Multi-table join (3+ tables)
  E01-E05  Subquery / CTE
  F01-F05  Window function

All queries:
  - Use PascalCase double-quoted Chinook identifiers
  - Have ORDER BY for deterministic result sets
  - Have been verified to return rows against the live DB
"""

GOLD_QUERIES: list[dict] = [
    # ── A: Simple filter ────────────────────────────────────────────────────
    {
        "id": "A01",
        "category": "filter",
        "question": "List tracks longer than 5 minutes with their duration.",
        "gold_sql": (
            'SELECT "Name", "Milliseconds" '
            'FROM "Track" '
            'WHERE "Milliseconds" > 300000 '
            'ORDER BY "Milliseconds" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "A02",
        "category": "filter",
        "question": "Show all customers from Brazil.",
        "gold_sql": (
            'SELECT "FirstName", "LastName", "City", "Email" '
            'FROM "Customer" '
            "WHERE \"Country\" ILIKE 'Brazil' "
            'ORDER BY "LastName", "FirstName" '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "A03",
        "category": "filter",
        "question": "Show all invoices from 2021.",
        "gold_sql": (
            'SELECT "InvoiceId", "CustomerId", "InvoiceDate", "Total" '
            'FROM "Invoice" '
            'WHERE EXTRACT(YEAR FROM "InvoiceDate") = 2021 '
            'ORDER BY "InvoiceDate" '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "A04",
        "category": "filter",
        "question": "Show tracks priced above $0.99.",
        "gold_sql": (
            'SELECT "Name", "UnitPrice" '
            'FROM "Track" '
            'WHERE "UnitPrice" > 0.99 '
            'ORDER BY "UnitPrice" DESC, "Name" '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "A05",
        "category": "filter",
        "question": "List employees hired after January 1st 2003.",
        "gold_sql": (
            'SELECT "FirstName", "LastName", "Title", "HireDate" '
            'FROM "Employee" '
            "WHERE \"HireDate\" > '2003-01-01' "
            'ORDER BY "HireDate" '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    # ── B: Aggregation ──────────────────────────────────────────────────────
    {
        "id": "B01",
        "category": "aggregation",
        "question": "How many tracks does each genre have?",
        "gold_sql": (
            'SELECT g."Name" AS "Genre", COUNT(t."TrackId") AS "TrackCount" '
            'FROM "Genre" g '
            'JOIN "Track" t ON g."GenreId" = t."GenreId" '
            'GROUP BY g."GenreId", g."Name" '
            'ORDER BY "TrackCount" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "B02",
        "category": "aggregation",
        "question": "What is the total revenue by billing country?",
        "gold_sql": (
            'SELECT "BillingCountry", SUM("Total") AS "Revenue" '
            'FROM "Invoice" '
            'GROUP BY "BillingCountry" '
            'ORDER BY "Revenue" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "B03",
        "category": "aggregation",
        "question": "What is the average track duration for each genre?",
        "gold_sql": (
            'SELECT g."Name" AS "Genre", AVG(t."Milliseconds") AS "AvgDurationMs" '
            'FROM "Genre" g '
            'JOIN "Track" t ON g."GenreId" = t."GenreId" '
            'GROUP BY g."GenreId", g."Name" '
            'ORDER BY "AvgDurationMs" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "B04",
        "category": "aggregation",
        "question": "Which are the top 10 artists by number of albums?",
        "gold_sql": (
            'SELECT ar."Name" AS "Artist", COUNT(al."AlbumId") AS "AlbumCount" '
            'FROM "Artist" ar '
            'JOIN "Album" al ON ar."ArtistId" = al."ArtistId" '
            'GROUP BY ar."ArtistId", ar."Name" '
            'ORDER BY "AlbumCount" DESC '
            "LIMIT 10"
        ),
        "expected_min_rows": 10,
    },
    {
        "id": "B05",
        "category": "aggregation",
        "question": "Show the invoice count and revenue for each year.",
        "gold_sql": (
            'SELECT EXTRACT(YEAR FROM "InvoiceDate")::INT AS "Year", '
            'COUNT("InvoiceId") AS "InvoiceCount", '
            'ROUND(SUM("Total")::NUMERIC, 2) AS "Revenue" '
            'FROM "Invoice" '
            'GROUP BY "Year" '
            'ORDER BY "Year" '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    # ── C: Single join ──────────────────────────────────────────────────────
    {
        "id": "C01",
        "category": "join",
        "question": "List all albums with their artist name.",
        "gold_sql": (
            'SELECT ar."Name" AS "Artist", al."Title" AS "Album" '
            'FROM "Artist" ar '
            'JOIN "Album" al ON ar."ArtistId" = al."ArtistId" '
            'ORDER BY ar."Name", al."Title" '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "C02",
        "category": "join",
        "question": "Show each customer's total spending.",
        "gold_sql": (
            'SELECT c."CustomerId", c."FirstName", c."LastName", '
            'ROUND(SUM(i."Total")::NUMERIC, 2) AS "TotalSpent" '
            'FROM "Customer" c '
            'JOIN "Invoice" i ON c."CustomerId" = i."CustomerId" '
            'GROUP BY c."CustomerId", c."FirstName", c."LastName" '
            'ORDER BY "TotalSpent" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "C03",
        "category": "join",
        "question": "List tracks with their genre name and duration.",
        "gold_sql": (
            'SELECT t."Name" AS "Track", g."Name" AS "Genre", t."Milliseconds" '
            'FROM "Track" t '
            'JOIN "Genre" g ON t."GenreId" = g."GenreId" '
            'ORDER BY t."Name" '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "C04",
        "category": "join",
        "question": "Show invoices with the customer first and last name.",
        "gold_sql": (
            'SELECT i."InvoiceId", c."FirstName", c."LastName", '
            'i."InvoiceDate", i."Total" '
            'FROM "Invoice" i '
            'JOIN "Customer" c ON i."CustomerId" = c."CustomerId" '
            'ORDER BY i."InvoiceDate" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "C05",
        "category": "join",
        "question": "How many tracks does each playlist contain?",
        "gold_sql": (
            'SELECT p."Name" AS "Playlist", COUNT(pt."TrackId") AS "TrackCount" '
            'FROM "Playlist" p '
            'JOIN "PlaylistTrack" pt ON p."PlaylistId" = pt."PlaylistId" '
            'GROUP BY p."PlaylistId", p."Name" '
            'ORDER BY "TrackCount" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    # ── D: Multi-table join ─────────────────────────────────────────────────
    {
        "id": "D01",
        "category": "multi_join",
        "question": "Show the top 20 artists by number of tracks.",
        "gold_sql": (
            'SELECT ar."Name" AS "Artist", COUNT(t."TrackId") AS "TrackCount" '
            'FROM "Artist" ar '
            'JOIN "Album" al ON ar."ArtistId" = al."ArtistId" '
            'JOIN "Track" t ON al."AlbumId" = t."AlbumId" '
            'GROUP BY ar."ArtistId", ar."Name" '
            'ORDER BY "TrackCount" DESC '
            "LIMIT 20"
        ),
        "expected_min_rows": 20,
    },
    {
        "id": "D02",
        "category": "multi_join",
        "question": "Which are the top 10 artists by total revenue?",
        "gold_sql": (
            'SELECT ar."Name" AS "Artist", '
            'ROUND(SUM(il."UnitPrice" * il."Quantity")::NUMERIC, 2) AS "Revenue" '
            'FROM "Artist" ar '
            'JOIN "Album" al ON ar."ArtistId" = al."ArtistId" '
            'JOIN "Track" t ON al."AlbumId" = t."AlbumId" '
            'JOIN "InvoiceLine" il ON t."TrackId" = il."TrackId" '
            'GROUP BY ar."ArtistId", ar."Name" '
            'ORDER BY "Revenue" DESC '
            "LIMIT 10"
        ),
        "expected_min_rows": 10,
    },
    {
        "id": "D03",
        "category": "multi_join",
        "question": "Show total revenue per genre.",
        "gold_sql": (
            'SELECT g."Name" AS "Genre", '
            'ROUND(SUM(il."UnitPrice" * il."Quantity")::NUMERIC, 2) AS "Revenue" '
            'FROM "Genre" g '
            'JOIN "Track" t ON g."GenreId" = t."GenreId" '
            'JOIN "InvoiceLine" il ON t."TrackId" = il."TrackId" '
            'GROUP BY g."GenreId", g."Name" '
            'ORDER BY "Revenue" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "D04",
        "category": "multi_join",
        "question": "List tracks with their artist, album, and genre.",
        "gold_sql": (
            'SELECT t."Name" AS "Track", ar."Name" AS "Artist", '
            'al."Title" AS "Album", g."Name" AS "Genre" '
            'FROM "Track" t '
            'JOIN "Album" al ON t."AlbumId" = al."AlbumId" '
            'JOIN "Artist" ar ON al."ArtistId" = ar."ArtistId" '
            'JOIN "Genre" g ON t."GenreId" = g."GenreId" '
            'ORDER BY ar."Name", al."Title", t."Name" '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "D05",
        "category": "multi_join",
        "question": "Show each sales rep's invoice count and total revenue.",
        "gold_sql": (
            'SELECT e."FirstName", e."LastName", '
            'COUNT(i."InvoiceId") AS "InvoiceCount", '
            'ROUND(SUM(i."Total")::NUMERIC, 2) AS "TotalRevenue" '
            'FROM "Employee" e '
            'JOIN "Customer" c ON e."EmployeeId" = c."SupportRepId" '
            'JOIN "Invoice" i ON c."CustomerId" = i."CustomerId" '
            'GROUP BY e."EmployeeId", e."FirstName", e."LastName" '
            'ORDER BY "TotalRevenue" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    # ── E: Subquery / CTE ───────────────────────────────────────────────────
    {
        "id": "E01",
        "category": "subquery",
        "question": "List artists who have more than 5 albums.",
        "gold_sql": (
            'SELECT ar."Name" AS "Artist", COUNT(al."AlbumId") AS "AlbumCount" '
            'FROM "Artist" ar '
            'JOIN "Album" al ON ar."ArtistId" = al."ArtistId" '
            'GROUP BY ar."ArtistId", ar."Name" '
            'HAVING COUNT(al."AlbumId") > 5 '
            'ORDER BY "AlbumCount" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "E02",
        "category": "subquery",
        "question": "Which customers have spent more than the average customer?",
        "gold_sql": (
            "WITH avg_spending AS ("
            'SELECT AVG("Total") AS avg_total FROM "Invoice"'
            ") "
            'SELECT c."FirstName", c."LastName", '
            'ROUND(SUM(i."Total")::NUMERIC, 2) AS "TotalSpent" '
            'FROM "Customer" c '
            'JOIN "Invoice" i ON c."CustomerId" = i."CustomerId" '
            'GROUP BY c."CustomerId", c."FirstName", c."LastName" '
            "HAVING SUM(i.\"Total\") > (SELECT avg_total FROM avg_spending) "
            'ORDER BY "TotalSpent" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "E03",
        "category": "subquery",
        "question": "Show albums that have more than 15 tracks.",
        "gold_sql": (
            'SELECT al."Title" AS "Album", ar."Name" AS "Artist", '
            'COUNT(t."TrackId") AS "TrackCount" '
            'FROM "Album" al '
            'JOIN "Artist" ar ON al."ArtistId" = ar."ArtistId" '
            'JOIN "Track" t ON al."AlbumId" = t."AlbumId" '
            'GROUP BY al."AlbumId", al."Title", ar."Name" '
            'HAVING COUNT(t."TrackId") > 15 '
            'ORDER BY "TrackCount" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "E04",
        "category": "subquery",
        "question": "Which tracks appear in more than 3 playlists?",
        "gold_sql": (
            'SELECT t."Name" AS "Track", COUNT(pt."PlaylistId") AS "PlaylistCount" '
            'FROM "Track" t '
            'JOIN "PlaylistTrack" pt ON t."TrackId" = pt."TrackId" '
            'GROUP BY t."TrackId", t."Name" '
            'HAVING COUNT(pt."PlaylistId") > 3 '
            'ORDER BY "PlaylistCount" DESC, t."Name" '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "E05",
        "category": "subquery",
        "question": "Show employees who support more than 15 customers.",
        "gold_sql": (
            'SELECT e."FirstName", e."LastName", COUNT(c."CustomerId") AS "CustomerCount" '
            'FROM "Employee" e '
            'JOIN "Customer" c ON e."EmployeeId" = c."SupportRepId" '
            'GROUP BY e."EmployeeId", e."FirstName", e."LastName" '
            'HAVING COUNT(c."CustomerId") > 15 '
            'ORDER BY "CustomerCount" DESC '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    # ── F: Window function ──────────────────────────────────────────────────
    {
        "id": "F01",
        "category": "window",
        "question": "Rank artists by number of tracks.",
        "gold_sql": (
            'SELECT ar."Name" AS "Artist", COUNT(t."TrackId") AS "TrackCount", '
            'RANK() OVER (ORDER BY COUNT(t."TrackId") DESC) AS "Rank" '
            'FROM "Artist" ar '
            'JOIN "Album" al ON ar."ArtistId" = al."ArtistId" '
            'JOIN "Track" t ON al."AlbumId" = t."AlbumId" '
            'GROUP BY ar."ArtistId", ar."Name" '
            'ORDER BY "Rank" '
            "LIMIT 20"
        ),
        "expected_min_rows": 20,
    },
    {
        "id": "F02",
        "category": "window",
        "question": "Show invoices with a running total of revenue ordered by date.",
        "gold_sql": (
            'SELECT "InvoiceDate", "Total", '
            'ROUND(SUM("Total") OVER ('
            'ORDER BY "InvoiceDate" '
            'ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW'
            ')::NUMERIC, 2) AS "RunningTotal" '
            'FROM "Invoice" '
            'ORDER BY "InvoiceDate" '
            "LIMIT 100"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "F03",
        "category": "window",
        "question": "Rank customers by spending within each country.",
        "gold_sql": (
            "WITH ranked AS ("
            'SELECT c."FirstName", c."LastName", c."Country", '
            'ROUND(SUM(i."Total")::NUMERIC, 2) AS "TotalSpent", '
            'RANK() OVER (PARTITION BY c."Country" ORDER BY SUM(i."Total") DESC) '
            'AS "RankInCountry" '
            'FROM "Customer" c '
            'JOIN "Invoice" i ON c."CustomerId" = i."CustomerId" '
            'GROUP BY c."CustomerId", c."FirstName", c."LastName", c."Country"'
            ") "
            'SELECT "FirstName", "LastName", "Country", "TotalSpent", "RankInCountry" '
            "FROM ranked "
            'ORDER BY "Country", "RankInCountry" '
            "LIMIT 1000"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "F04",
        "category": "window",
        "question": "Show each track's duration vs the average duration for its genre.",
        "gold_sql": (
            'SELECT t."Name" AS "Track", t."Milliseconds", g."Name" AS "Genre", '
            'ROUND(AVG(t."Milliseconds") OVER (PARTITION BY t."GenreId")::NUMERIC, 0) '
            'AS "AvgGenreDurationMs" '
            'FROM "Track" t '
            'JOIN "Genre" g ON t."GenreId" = g."GenreId" '
            'ORDER BY g."Name", t."Name" '
            "LIMIT 100"
        ),
        "expected_min_rows": 1,
    },
    {
        "id": "F05",
        "category": "window",
        "question": "Number tracks within each album ordered by duration descending.",
        "gold_sql": (
            'SELECT t."Name" AS "Track", al."Title" AS "Album", t."Milliseconds", '
            'ROW_NUMBER() OVER (PARTITION BY t."AlbumId" ORDER BY t."Milliseconds" DESC) '
            'AS "RowNum" '
            'FROM "Track" t '
            'JOIN "Album" al ON t."AlbumId" = al."AlbumId" '
            'ORDER BY al."Title", "RowNum" '
            "LIMIT 100"
        ),
        "expected_min_rows": 1,
    },
]

GOLD_BY_ID: dict[str, dict] = {q["id"]: q for q in GOLD_QUERIES}
