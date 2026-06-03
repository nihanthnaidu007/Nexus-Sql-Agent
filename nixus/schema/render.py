"""Render an introspected Table into text suitable for embedding.

This rendering is where retrieval quality lives: it is the text that gets
embedded and stored as a schema_embeddings row's ``description``, and later read
back by ``retrieve_schema`` to ground SQL generation. The handwritten Chinook
descriptions are the richness target — so we render the table comment (human
semantic gold), every column with its type / nullability / PK / enum values, and
foreign-key relationships as readable join sentences (the single most useful hint
for SQL generation).

Grain: ONE text block per table (mirrors the handwritten path and the
schema_embeddings UNIQUE(table_name) shape). Wide tables render ALL columns;
chunking is only considered if a single block would exceed the embedding token
limit (see embed.py) — never truncate.
"""
from __future__ import annotations

from nixus.schema.models import ForeignKey, Table


def qualified_name(table: Table) -> str:
    """Schema-qualified only when not in public, matching the handwritten path's
    bare names for public tables (e.g. "Track", but "billing.invoice")."""
    return table.name if table.schema == "public" else f"{table.schema}.{table.name}"


def _column_phrase(col) -> str:
    parts = [col.data_type, "nullable" if col.is_nullable else "not null"]
    if col.is_primary_key:
        parts.append("primary key")
    if col.enum_values:
        parts.append("enum: " + ", ".join(col.enum_values))
    phrase = f"{col.name} ({', '.join(parts)})"
    if col.comment:
        phrase += f" — {col.comment}"
    return phrase


def _fk_sentences(table: Table, foreign_keys: list[ForeignKey]) -> list[str]:
    """Readable join sentences for FKs where THIS table is the source.

    A composite FK becomes one sentence per paired column, preserving the
    introspected ordering (from_columns[i] references to_columns[i]).
    """
    sentences: list[str] = []
    for fk in foreign_keys:
        if fk.from_schema != table.schema or fk.from_table != table.name:
            continue
        to = fk.to_table if fk.to_schema == "public" else f"{fk.to_schema}.{fk.to_table}"
        for from_col, to_col in zip(fk.from_columns, fk.to_columns):
            sentences.append(f"{table.name}.{from_col} references {to}.{to_col}")
    return sentences


def table_to_text(table: Table, foreign_keys: list[ForeignKey]) -> str:
    """Render one table (+ its outgoing FKs) into a descriptive embeddable block."""
    name = qualified_name(table)
    lines = [f'Table "{name}".']

    if table.comment:
        lines.append(table.comment)

    if table.columns:
        col_list = "; ".join(_column_phrase(c) for c in table.columns)
        lines.append(f"It has {len(table.columns)} columns: {col_list}.")
    else:
        lines.append("It has no columns.")

    if table.primary_key:
        lines.append(f"Primary key: {', '.join(table.primary_key)}.")

    fks = _fk_sentences(table, foreign_keys)
    if fks:
        lines.append("Foreign keys: " + "; ".join(fks) + ".")

    return "\n".join(lines)
