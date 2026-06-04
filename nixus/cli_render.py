"""Terminal rendering for the NIXUS CLI — pure formatting, no logic.

Extracted from ``nixus.cli`` to keep that adapter thin: this module only turns the
core's response state into terminal text (an aligned table, the insight, the
confidence verdict WITH its reasons, a calm refusal). It decides nothing — the
core already decided the outcome, the SQL, and the confidence; this just prints
it. No database, no graph, no query/scope/grounding logic lives here.
"""
from __future__ import annotations

ROW_CAP = 50  # don't flood the terminal; note the true total for larger sets.


def _cell(value) -> str:
    return "NULL" if value is None else str(value)


def format_table(columns: list, rows: list) -> str:
    """A simple aligned text table (stdlib only — no new dependency just to print
    a grid). ``rows`` are dicts keyed by ``columns`` (the core's row shape)."""
    if not rows:
        return "(no rows)"
    if not columns:
        columns = list(rows[0].keys())
    str_rows = [[_cell(r.get(c)) for c in columns] for r in rows]
    widths = [len(str(c)) for c in columns]
    for sr in str_rows:
        for i, v in enumerate(sr):
            widths[i] = max(widths[i], len(v))

    def line(cells) -> str:
        return " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(cells))

    sep = "-+-".join("-" * w for w in widths)
    return "\n".join([line(columns), sep, *(line(sr) for sr in str_rows)])


def render_answer(state: dict) -> None:
    """Render an ANSWERED outcome: the SQL that ran, the rows as a text table, the
    insight, and the confidence LEVEL with its reasons (the visible honesty)."""
    sql = state.get("generated_sql") or ""
    exec_res = state.get("execution_result") or {}
    rows = exec_res.get("rows") or []
    columns = exec_res.get("columns") or []
    total = exec_res.get("row_count", len(rows))
    insight = state.get("explanation") or ""
    confidence = state.get("confidence") or "UNKNOWN"
    reasons = state.get("confidence_reasons") or []

    print("SQL")
    print("───")
    print(sql)
    print()
    print("Result")
    print("──────")
    print(format_table(columns, rows[:ROW_CAP]))
    if total > ROW_CAP:
        print(f"… showing first {ROW_CAP} of {total} rows.")
    print()
    if insight:
        print("Insight")
        print("───────")
        print(insight)
        print()
    # Surface the reasons, not just the label — the visible honesty is the point.
    print(f"Confidence: {confidence}")
    for r in reasons:
        print(f"  • {r}")


def render_refusal(state: dict) -> None:
    """A refusal is calm and reasoned — no SQL, no rows, no stack trace."""
    outcome = state.get("outcome") or "REFUSED"
    reason = (
        state.get("reason")
        or state.get("scope_message")
        or state.get("explanation")
        or "The request was refused."
    )
    print(f"Refused — {outcome}")
    print(reason)
