"""Generic re-embed command — (re)build schema_embeddings from the live target_db.

    python -m nixus.schema.reembed                 # always full wipe + rebuild
    python -m nixus.schema.reembed --skip-if-exists # no-op if already populated

Introspects whatever ``target_db`` is configured to point at, renders + embeds
every table, and FULL wipe-and-rebuilds schema_embeddings on state_db. This is
THE (and only) way schema_embeddings is populated: generic (no Chinook / hardcoded
names), safe to re-run (idempotent via wipe+rebuild), reads target read-only and
writes state.

``--skip-if-exists`` makes it safe in first-run/startup scripts: if the store is
already populated it does nothing (no embedding API calls on every boot), matching
the old seed script's flag. Without the flag it always rebuilds — what a user runs
after the target schema changes.

Thin by design: it just wires the engines into the pipeline (nixus.schema.embed).
"""
from __future__ import annotations

import argparse
import asyncio

from dotenv import load_dotenv

load_dotenv()

from nixus.db.connection import get_state_engine, get_target_engine
from nixus.db.schema_store import get_schema_count
from nixus.schema.embed import embed_target_schema


async def _run(skip_if_exists: bool = False) -> int:
    if skip_if_exists:
        existing = await get_schema_count()
        if existing > 0:
            print(f"◈ schema_embeddings already populated ({existing} rows). Skipping.")
            return existing

    target_engine = get_target_engine()
    state_engine = get_state_engine()
    print("◈ Re-embedding schema_embeddings from the live target database (introspection)...")
    rows = await embed_target_schema(target_engine, state_engine)
    # One row per table (no chunking needed), so introspected tables == rows.
    print(f"◈ Introspected {rows} tables; wrote {rows} embedding rows (full wipe + rebuild).")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-embed schema_embeddings from target_db via introspection.")
    parser.add_argument(
        "--skip-if-exists",
        action="store_true",
        help="No-op when schema_embeddings already has rows (safe for repeated boots).",
    )
    args = parser.parse_args()
    asyncio.run(_run(skip_if_exists=args.skip_if_exists))


if __name__ == "__main__":
    main()
