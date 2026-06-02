from sqlalchemy import text
from nixus.db.connection import engine


async def search_schemas(embedding: list, limit: int = 6) -> list:
    """Async pgvector similarity search on schema_embeddings."""
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    async with engine.connect() as conn:
        rows = await conn.execute(text("""
            SELECT
                table_name,
                description,
                columns_json,
                sample_values_json,
                1 - (embedding <=> CAST(:query AS vector)) AS similarity
            FROM schema_embeddings
            ORDER BY embedding <=> CAST(:query AS vector)
            LIMIT :limit
        """), {"query": vec_str, "limit": limit})
        results = rows.fetchall()

    return [
        {
            "table_name": r[0],
            "description": r[1],
            "columns_json": r[2],
            "sample_values_json": r[3],
            "similarity": float(r[4]),
        }
        for r in results
    ]


async def store_schema_embedding(
    table_name: str,
    description: str,
    columns_json: str,
    sample_values_json: str,
    embedding: list,
) -> None:
    """Store or update a schema embedding."""
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO schema_embeddings
                (table_name, description, columns_json,
                 sample_values_json, embedding)
            VALUES
                (:table_name, :description, :columns_json,
                 :sample_values_json, CAST(:embedding AS vector))
            ON CONFLICT (table_name) DO UPDATE SET
                description       = EXCLUDED.description,
                columns_json      = EXCLUDED.columns_json,
                sample_values_json = EXCLUDED.sample_values_json,
                embedding         = EXCLUDED.embedding
        """), {
            "table_name": table_name,
            "description": description,
            "columns_json": columns_json,
            "sample_values_json": sample_values_json,
            "embedding": vec_str,
        })


async def get_schema_count() -> int:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM schema_embeddings"))
        return result.scalar() or 0


async def retrieve_relevant_schemas(query: str, top_k: int = 6) -> list:
    """Embed the natural-language query and run a similarity search.

    Convenience wrapper used by retrieve_schema_node and ad-hoc tooling
    that wants to go from query string → ranked tables in one call.
    """
    from nixus.utils.embeddings import embed_text

    embedding = await embed_text(query)
    return await search_schemas(embedding, limit=top_k)
