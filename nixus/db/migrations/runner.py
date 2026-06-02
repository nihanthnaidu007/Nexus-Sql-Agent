"""Lightweight numbered-SQL migration runner.

Applies ``NNNN_*.sql`` files from this directory in numeric order, exactly once
each, each inside its own transaction, recording applied versions in a
``schema_migrations`` tracking table. Already-applied migrations are skipped.

Async by design (asyncpg — the same driver the app's async engine uses), so
Phase 2 can call it from the async startup path; a thin sync wrapper is provided
for CLI/`schema_init` use. The target database is read from the single config
source (`nixus.config.settings.database_url`) at call time, so a one-shot
``DATABASE_URL=...`` override (e.g. for the fresh-DB rebuild test) is honored.

Scope is the APPLICATION schema only. LangGraph's checkpointer tables are owned
by ``AsyncPostgresSaver.setup()`` and are never created, altered, or tracked here.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

import asyncpg

from nixus.config import settings

MIGRATIONS_DIR = Path(__file__).resolve().parent
_VERSION_RE = re.compile(r"^(\d+)_.*\.sql$")

_CREATE_TRACKING = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    filename   TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _pg_dsn() -> str:
    """Plain ``postgresql://`` DSN for asyncpg, from the single config source.

    Strips any SQLAlchemy driver suffix so asyncpg.connect accepts it regardless
    of how DATABASE_URL was written.
    """
    url = settings.database_url or ""
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg2://", "postgresql://")
        .replace("postgres://", "postgresql://", 1)
    )


def discover_migrations() -> list[tuple[str, Path]]:
    """Return ``[(version, path), ...]`` for ``NNNN_*.sql``, sorted by numeric prefix."""
    found: list[tuple[str, Path]] = []
    for p in MIGRATIONS_DIR.glob("*.sql"):
        m = _VERSION_RE.match(p.name)
        if m:
            found.append((m.group(1), p))
    found.sort(key=lambda vp: int(vp[0]))
    return found


async def applied_versions() -> list[str]:
    """Return the sorted list of applied migration versions (creates the tracking table if absent)."""
    conn = await asyncpg.connect(_pg_dsn())
    try:
        await conn.execute(_CREATE_TRACKING)
        rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
        return [r["version"] for r in rows]
    finally:
        await conn.close()


async def apply_migrations() -> list[str]:
    """Apply every not-yet-applied migration in numeric order.

    Each migration runs in its own transaction together with its
    ``schema_migrations`` insert, so a migration is recorded only if its SQL
    succeeds. On failure, that migration is rolled back, no later migrations run,
    and the error propagates. Returns the versions applied during this call.
    """
    conn = await asyncpg.connect(_pg_dsn())
    newly_applied: list[str] = []
    try:
        await conn.execute(_CREATE_TRACKING)
        done = {
            r["version"]
            for r in await conn.fetch("SELECT version FROM schema_migrations")
        }
        for version, path in discover_migrations():
            if version in done:
                continue
            sql = path.read_text()
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, filename) VALUES ($1, $2)",
                    version,
                    path.name,
                )
            newly_applied.append(version)
    finally:
        await conn.close()
    return newly_applied


def apply_migrations_sync() -> list[str]:
    """Synchronous wrapper around :func:`apply_migrations` for CLI / sync callers."""
    return asyncio.run(apply_migrations())
