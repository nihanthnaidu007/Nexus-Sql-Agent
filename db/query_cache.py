import json
from sqlalchemy import text
from db.connection import engine


async def search_cache(embedding: list, threshold: float = 0.92) -> dict | None:
    """Async semantic cache lookup."""
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    async with engine.connect() as conn:
        row = await conn.execute(text("""
            SELECT
                id,
                generated_sql,
                result_preview_json,
                row_count,
                execution_time_ms,
                chart_type,
                explanation,
                1 - (query_embedding <=> CAST(:query AS vector)) AS similarity
            FROM query_cache
            WHERE 1 - (query_embedding <=> CAST(:query AS vector)) >= :threshold
            ORDER BY query_embedding <=> CAST(:query AS vector)
            LIMIT 1
        """), {"query": vec_str, "threshold": threshold})
        result = row.fetchone()

    if not result:
        return None

    preview = result[2]
    if isinstance(preview, str):
        try:
            preview = json.loads(preview)
        except Exception:
            preview = []

    return {
        "id": result[0],
        "generated_sql": result[1],
        "result_preview": preview,
        "row_count": result[3],
        "execution_time_ms": result[4],
        "chart_type": result[5],
        "explanation": result[6],
        "similarity": float(result[7]),
    }


async def increment_hit_count(cache_id: int) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("""
            UPDATE query_cache
            SET hit_count = hit_count + 1,
                last_accessed = NOW()
            WHERE id = :id
        """), {"id": cache_id})


async def store_cache_entry(
    user_query: str,
    query_embedding: list,
    generated_sql: str,
    result_preview: list,
    row_count: int,
    execution_time_ms: float,
    chart_type: str | None,
    explanation: str,
) -> None:
    vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO query_cache (
                user_query, query_embedding, generated_sql,
                result_preview_json, row_count, execution_time_ms,
                chart_type, explanation
            ) VALUES (
                :query, CAST(:emb AS vector), :sql,
                :preview, :rows, :ms, :chart, :explain
            )
        """), {
            "query": user_query,
            "emb": vec_str,
            "sql": generated_sql,
            "preview": json.dumps(result_preview, default=str),
            "rows": row_count,
            "ms": execution_time_ms,
            "chart": chart_type,
            "explain": explanation,
        })


async def get_cache_stats() -> dict:
    async with engine.connect() as conn:
        row = await conn.execute(text("""
            SELECT
                COUNT(*) AS entries,
                COALESCE(SUM(hit_count), 0) AS total_hits
            FROM query_cache
        """))
        r = row.fetchone()
    entries = r[0] or 0
    hits = int(r[1] or 0)
    total_requests = entries + hits
    hit_rate = round((hits / total_requests * 100), 1) if total_requests > 0 else 0.0
    return {"entries": entries, "total_hits": hits, "hit_rate": hit_rate}
