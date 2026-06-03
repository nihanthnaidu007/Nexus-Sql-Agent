"""Generic re-embed command — (re)build schema_embeddings from the live target_db.

    python -m nixus.schema.reembed

Introspects whatever ``target_db`` is configured to point at, renders + embeds
every table, and FULL wipe-and-rebuilds schema_embeddings on state_db. It is the
command a user runs after their schema changes: generic (no Chinook / hardcoded
names), safe to re-run (idempotent via wipe+rebuild), reads target read-only and
writes state.

Thin by design: it just wires the engines into the pipeline (nixus.schema.embed).
"""
from __future__ import annotations

import asyncio

from dotenv import load_dotenv

load_dotenv()

from nixus.db.connection import get_state_engine, get_target_engine
from nixus.schema.embed import embed_target_schema


async def _run() -> int:
    target_engine = get_target_engine()
    state_engine = get_state_engine()
    print("◈ Re-embedding schema_embeddings from the live target database (introspection)...")
    rows = await embed_target_schema(target_engine, state_engine)
    # One row per table (no chunking needed), so introspected tables == rows.
    print(f"◈ Introspected {rows} tables; wrote {rows} embedding rows (full wipe + rebuild).")
    return rows


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
