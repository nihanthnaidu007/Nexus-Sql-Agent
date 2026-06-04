"""Tests for the NIXUS CLI ADAPTER (prompt 7.1).

The CLI calls the core (``query_service.run_query``); these tests exercise the
ADAPTER's job — argument parsing, outcome rendering, the clarification loop
control, and the thin-adapter boundary — by mocking the core so no DB/LLM runs.
The point under test is that each outcome the core can return is rendered
faithfully for a terminal, that the clarification loop is interactive on a TTY but
single-shot (no hang) off one, that it terminates, and that the adapter does NOT
reimplement or bypass the core.
"""
import pathlib
from unittest.mock import AsyncMock, patch

import pytest

from nixus import cli


@pytest.fixture(autouse=True)
def _no_real_checkpointer():
    """The adapter opens/closes the LangGraph checkpoint pool around a query (the
    same lifecycle the API runs in its lifespan). Mock it so tests never touch a
    real database — we are testing the ADAPTER, with the core mocked."""
    with patch.object(cli, "init_checkpointer", AsyncMock()), \
         patch.object(cli, "aclose_checkpointer", AsyncMock()):
        yield


# ── fixtures: canned core outcomes (the shape run_query returns) ─────────────
def _answered_state():
    return {
        "outcome": "ANSWERED",
        "generated_sql": 'SELECT count(*) AS n FROM "Track"',
        "execution_result": {
            "rows": [{"n": 3503}],
            "columns": ["n"],
            "row_count": 1,
        },
        "explanation": "There are 3503 tracks in the catalog.",
        "confidence": "MEDIUM",
        "confidence_reasons": [
            "This query required clarification, so its intent was not unambiguous."
        ],
    }


def _needs_clarification_state():
    return {
        "outcome": "NEEDS_CLARIFICATION",
        "clarifying_question": "Do you mean tracks or albums?",
        "reason": "",
    }


def _refused_state(outcome="REFUSED_OUT_OF_SCOPE", reason="That is not a data question."):
    return {"outcome": outcome, "reason": reason, "generated_sql": "", "execution_result": None}


# ── ANSWERED: SQL + table + insight + confidence WITH reasons ────────────────
def test_query_answered_renders_sql_table_insight_confidence(capsys):
    with patch.object(cli, "run_query", AsyncMock(return_value=_answered_state())):
        rc = cli.main(["query", "how many tracks are there?"])
    out = capsys.readouterr().out
    assert rc == 0
    assert 'SELECT count(*) AS n FROM "Track"' in out  # the SQL that ran
    assert "3503" in out                                # a result table cell
    assert "There are 3503 tracks" in out              # the insight
    assert "Confidence: MEDIUM" in out                 # the level
    # the reason text is surfaced, not just the label (the honesty is the point)
    assert "required clarification" in out


# ── NEEDS_CLARIFICATION off a TTY: print question + exit, never hang ─────────
def test_query_clarification_non_tty_is_single_shot(capsys):
    with patch.object(cli, "run_query", AsyncMock(return_value=_needs_clarification_state())), \
         patch("sys.stdin.isatty", return_value=False):
        rc = cli.main(["query", "show me the data"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Do you mean tracks or albums?" in out
    assert "re-run" in out.lower()  # the single-shot guidance


# ── NEEDS_CLARIFICATION on a TTY: read the answer, re-call with context ──────
def test_query_clarification_interactive_then_answered(capsys):
    core = AsyncMock(side_effect=[_needs_clarification_state(), _answered_state()])
    with patch.object(cli, "run_query", core), \
         patch("sys.stdin.isatty", return_value=True), \
         patch("builtins.input", return_value="tracks"):
        rc = cli.main(["query", "show me the data"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Do you mean tracks or albums?" in out
    assert "3503" in out  # resolved to the ANSWERED render
    # second call carried the accumulated clarification context + round bump
    second_kwargs = core.await_args_list[1].kwargs
    ctx = second_kwargs["clarification_context"]
    assert ctx["prior_clarifications"][0]["answer"] == "tracks"
    assert second_kwargs["clarification_round"] == 1


# ── REFUSED_*: print the reason; no SQL, no rows ────────────────────────────
@pytest.mark.parametrize("outcome,reason", [
    ("REFUSED_OUT_OF_SCOPE", "That is not a data question."),
    ("REFUSED_WRITE", "This is a read-only system; it will not modify data."),
])
def test_query_refusal_prints_reason_only(capsys, outcome, reason):
    with patch.object(cli, "run_query", AsyncMock(return_value=_refused_state(outcome, reason))):
        rc = cli.main(["query", "delete all artists"])
    out = capsys.readouterr().out
    assert rc == 0
    assert reason in out
    assert outcome in out
    assert "SELECT" not in out  # no SQL rendered for a refusal
    assert "Result" not in out  # no result table


# ── the clarification loop TERMINATES at REFUSED_AMBIGUOUS (no infinite loop) ─
def test_query_clarification_loop_terminates_at_ambiguous(capsys):
    core = AsyncMock(side_effect=[
        _needs_clarification_state(),
        _needs_clarification_state(),
        _refused_state("REFUSED_AMBIGUOUS", "Still ambiguous after two rounds."),
    ])
    with patch.object(cli, "run_query", core), \
         patch("sys.stdin.isatty", return_value=True), \
         patch("builtins.input", return_value="still vague"):
        rc = cli.main(["query", "show me the data"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "REFUSED_AMBIGUOUS" in out
    assert core.await_count == 3  # terminated, did not loop forever


# ── health: per-database status + non-zero exit on failure ──────────────────
def test_health_reports_per_database_status(capsys):
    with patch.object(cli, "get_state_engine", return_value=object()), \
         patch.object(cli, "get_target_engine", return_value=object()), \
         patch.object(cli, "_ping", AsyncMock(side_effect=[(True, None), (False, "connection refused")])):
        rc = cli.main(["health"])
    out = capsys.readouterr().out
    assert "state_db" in out and "OK" in out
    assert "target_db" in out and "FAIL" in out and "connection refused" in out
    assert rc == 1  # a genuinely unreachable DB is an error


def test_health_all_ok_exits_zero(capsys):
    with patch.object(cli, "get_state_engine", return_value=object()), \
         patch.object(cli, "get_target_engine", return_value=object()), \
         patch.object(cli, "_ping", AsyncMock(return_value=(True, None))):
        rc = cli.main(["health"])
    assert rc == 0
    assert capsys.readouterr().out.count("OK") == 2


# ── reembed: wraps the EXISTING pipeline, does not duplicate it ─────────────
def test_reembed_calls_existing_pipeline():
    with patch("nixus.schema.reembed._run", AsyncMock(return_value=7)) as run_pipeline:
        rc = cli.main(["reembed"])
    assert rc == 0
    run_pipeline.assert_awaited_once()


# ── thin-adapter guard: cli.py goes through the core, not around it ─────────
def test_cli_is_a_thin_adapter_not_a_reimplementation():
    src = pathlib.Path(cli.__file__).read_text()
    # Reuses THE core entry the API calls:
    assert "from nixus.services.query_service import run_query" in src
    # Does NOT import graph nodes / build its own graph run / reimplement scope or
    # confidence — those would mean the CLI diverges from the API.
    assert "nixus.graph.nodes" not in src
    assert "build_graph" not in src
    assert "ainvoke" not in src and "astream" not in src
    assert "assess_confidence" not in src
    assert "check_grounding" not in src
