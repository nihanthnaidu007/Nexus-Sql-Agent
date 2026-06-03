"""The introspection-based schema embedding pipeline.

``embed_target_schema`` runs the full chain for whatever ``target_engine`` points
at: introspect (2.2) -> render to text (render.py) -> embed (utils) -> write rows
into schema_embeddings on state_db (2.1 routing: read target, write state). It is
a FULL wipe-and-rebuild, transactional, and writes rows in the exact shape
``retrieve_schema`` already reads (table_name / description / columns_json /
sample_values_json), so retrieval consumes introspection rows identically to the
handwritten ones.

Per decision: NO sample values are captured — ``sample_values_json`` is left
null for introspection rows. This is structural metadata only.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncEngine

from nixus.db.schema_store import replace_schema_embeddings
from nixus.schema.introspect import introspect_schema
from nixus.schema.models import Table
from nixus.schema.render import qualified_name, table_to_text
from nixus.utils.embeddings import embed_texts

logger = logging.getLogger("nixus_sql.schema")

# text-embedding-3-small accepts ~8191 tokens. One rendered table block is tiny
# (even a 60-column table is a few thousand characters); embed_text already caps
# input length. If a single block ever approached the limit we would chunk by
# columns into multiple part-rows rather than truncate — not needed for any
# observed schema (Chinook tables are small), so no chunking is performed.


def _columns_payload(table: Table) -> str:
    """Structural columns_json from the typed columns (mirrors the handwritten
    columns_json shape: a list of per-column dicts)."""
    payload = []
    for c in table.columns:
        col: dict = {
            "name": c.name,
            "type": c.data_type,
            "nullable": c.is_nullable,
            "primary_key": c.is_primary_key,
            "description": c.comment,
        }
        if c.enum_values:
            col["enum_values"] = c.enum_values
        payload.append(col)
    return json.dumps(payload)


async def embed_target_schema(target_engine: AsyncEngine, state_engine: AsyncEngine) -> int:
    """Introspect target_db, render+embed each table, and rebuild schema_embeddings
    on state_db. Returns the number of embedding rows written (one per table).

    ``state_engine`` is accepted for symmetry/explicitness; the actual write goes
    through the state-bound store (schema_store), which already targets state_db.
    """
    schema = await introspect_schema(target_engine)

    descriptions: list[str] = []
    rows: list[dict] = []
    for table in schema.tables:
        text_block = table_to_text(table, schema.foreign_keys)
        descriptions.append(text_block)
        rows.append({
            "table_name": qualified_name(table),
            "description": text_block,
            "columns_json": _columns_payload(table),
            "sample_values_json": None,   # no sample values captured (by decision)
        })

    if not rows:
        logger.warning("Introspection found no tables in target_db; nothing to embed.")
        await replace_schema_embeddings([])
        return 0

    embeddings = await embed_texts(descriptions)
    for row, emb in zip(rows, embeddings):
        row["embedding"] = emb

    written = await replace_schema_embeddings(rows)
    logger.info(
        "Embedded target schema via introspection: %d tables -> %d rows.",
        len(schema.tables), written,
    )
    return written
