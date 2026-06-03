"""Schema drift detection: does the live target still match what is embedded?

``detect_drift`` introspects target_db live and compares its tables+columns
against the structure currently stored in schema_embeddings — a cheap, fast,
structural comparison (table and column NAMES), never a re-embed. It REPORTS and
ADVISES; it never auto-reembeds (embeddings cost API calls — that is the user's
call) and never crashes the app.

Mode: drift is authoritative for the introspection path (the embedded structure
came from the same introspection, so names line up). For the handwritten path the
embedded columns_json is a hand-curated SUBSET of the real columns, so structural
differences are EXPECTED — the report is then marked ``advisory`` so its output is
read as informational only.
"""
from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from nixus.config import settings
from nixus.db.schema_store import list_schema_rows
from nixus.schema.introspect import introspect_schema
from nixus.schema.render import qualified_name

logger = logging.getLogger("nixus_sql.schema")

REEMBED_COMMAND = "python -m nixus.schema.reembed"


class DriftReport(BaseModel):
    in_sync: bool
    schema_source: str
    advisory: bool                                   # True when not authoritative (handwritten)
    added_tables: list[str] = Field(default_factory=list)     # live has, store lacks
    removed_tables: list[str] = Field(default_factory=list)   # store has, live lacks
    added_columns: list[str] = Field(default_factory=list)    # "table.column" live has, store lacks
    removed_columns: list[str] = Field(default_factory=list)  # "table.column" store has, live lacks
    recommendation: str | None = None

    def summary(self) -> str:
        if self.in_sync:
            return "schema in sync with embeddings"
        bits = []
        if self.added_tables:
            bits.append(f"+tables {self.added_tables}")
        if self.removed_tables:
            bits.append(f"-tables {self.removed_tables}")
        if self.added_columns:
            bits.append(f"+columns {self.added_columns}")
        if self.removed_columns:
            bits.append(f"-columns {self.removed_columns}")
        return "; ".join(bits)


def _embedded_columns(columns_json: str) -> set[str]:
    try:
        cols = json.loads(columns_json) or []
    except Exception:
        return set()
    return {c.get("name") for c in cols if isinstance(c, dict) and c.get("name")}


async def detect_drift(target_engine: AsyncEngine, state_engine: AsyncEngine) -> DriftReport:
    """Compare the live target structure against the embedded structure."""
    advisory = settings.schema_source != "introspection"

    live_schema = await introspect_schema(target_engine)
    live = {qualified_name(t): {c.name for c in t.columns} for t in live_schema.tables}

    embedded_rows = await list_schema_rows()
    embedded = {r["table_name"]: _embedded_columns(r["columns_json"]) for r in embedded_rows}

    live_names, embedded_names = set(live), set(embedded)
    added_tables = sorted(live_names - embedded_names)
    removed_tables = sorted(embedded_names - live_names)

    added_columns: list[str] = []
    removed_columns: list[str] = []
    for tname in sorted(live_names & embedded_names):
        for col in sorted(live[tname] - embedded[tname]):
            added_columns.append(f"{tname}.{col}")
        for col in sorted(embedded[tname] - live[tname]):
            removed_columns.append(f"{tname}.{col}")

    in_sync = not (added_tables or removed_tables or added_columns or removed_columns)
    recommendation = None if in_sync else f"Run `{REEMBED_COMMAND}` to rebuild schema_embeddings."

    return DriftReport(
        in_sync=in_sync,
        schema_source=settings.schema_source,
        advisory=advisory,
        added_tables=added_tables,
        removed_tables=removed_tables,
        added_columns=added_columns,
        removed_columns=removed_columns,
        recommendation=recommendation,
    )


async def log_drift_at_startup(target_engine: AsyncEngine, state_engine: AsyncEngine) -> None:
    """Advisory, NON-FATAL startup check. Logs a warning if drift is detected;
    never raises (a broken/unreachable target must not crash the app)."""
    try:
        report = await detect_drift(target_engine, state_engine)
    except Exception:
        logger.exception("Schema drift check failed (non-fatal); continuing.")
        return

    if report.in_sync:
        logger.info("Schema drift check: in sync (schema_source=%s).", report.schema_source)
        return

    label = "advisory, handwritten path" if report.advisory else "introspection path"
    logger.warning(
        "Schema drift detected (%s): %s. %s",
        label, report.summary(), report.recommendation or "",
    )
