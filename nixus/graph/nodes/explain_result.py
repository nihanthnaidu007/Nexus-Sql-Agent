import json
import logging
from dotenv import load_dotenv
from datetime import datetime
from langchain_anthropic import ChatAnthropic

load_dotenv()

from nixus.db.fewshot_store import store_fewshot_example
from nixus.db.query_cache import store_cache_entry
from nixus.utils.embeddings import embed_text
from nixus.utils.confidence import compute_confidence_score
from nixus.utils.retry import llm_retry
from nixus.graph.state import SQLAgentState
from nixus.graph.explanation_check import is_overstated, describe_result_plainly

logger = logging.getLogger(__name__)

EXPLAIN_PROMPT = """You describe a SQL query result to a business user in plain, useful language.

Original question: {user_query}
SQL used: {sql}
Result: {result_summary}

Write 1-3 sentences that DESCRIBE what the returned rows actually contain. Be
specific and genuinely informative about THIS result set — not a thin row dump.

DO:
- Lead with the direct answer to the question using the concrete values in the
  rows: the top/bottom item, the key figures, the range across the rows, the
  row count, notable comparisons that are literally present (e.g. how the top
  few cluster, the leader vs. the rest).
- If the result is empty, say plainly that no rows matched. If there is a single
  row, describe just that row. If there are only a few rows, describe them
  without generalizing beyond them.

DO NOT:
- State causes about the world ("because", "due to", "driven by", "led to"). You
  may describe what the query did (e.g. "limited to 2023"), but never assert why
  a real-world number is the way it is.
- Speculate or infer real-world conclusions ("suggests", "implies", "indicates
  that [a business takeaway]", "likely", "probably", "reflects [a trend]").
- Predict or forecast ("will", "expected to", "going to", "trending toward").
- Recommend or advise ("should", "recommend", "consider doing").
- Generalize beyond the returned rows (no claims about all customers / products /
  periods when the result is a narrow slice).

Describe the result accurately and richly — but claim nothing the rows cannot prove."""

# Appended on the single regeneration when the first attempt editorialized. It
# quotes the markers that fired so the model corrects the specific violation.
STRICT_SUFFIX = """

IMPORTANT — your previous explanation editorialized: {triggers}. That is not
allowed. Do not state causes, predictions, or recommendations, and do not infer
real-world conclusions. Describe ONLY what the rows literally show: the values,
the ranges, and the row count."""


def now():
    return datetime.now().strftime("%H:%M:%S")


async def explain_result_node(state: SQLAgentState) -> SQLAgentState:
    state["current_node"] = "explain_result"
    llm = ChatAnthropic(
        model="claude-haiku-4-5",
        temperature=0.3,
        max_tokens=256,
    )

    result = state.get("execution_result") or {}
    rows = result.get("rows", [])
    row_count = result.get("row_count", 0)

    if state.get("served_from_cache") and state.get("cache_result"):
        cr = state["cache_result"]
        if cr.get("explanation"):
            state["explanation"] = cr["explanation"]
            state["confidence_score"] = compute_confidence_score(
                correction_attempts=0,
                result_quality_status="GOOD",
                syntax_warnings=[],
                served_from_cache=True,
                cache_similarity=cr.get("similarity", 0.9),
            )
            state["is_complete"] = True
            state["completed_nodes"].append("explain_result")
            state["stream_updates"].append({
                "timestamp": now(), "node": "explain_result",
                "message": f"Complete (cached) — confidence: {state['confidence_score']:.0%}",
                "status": "done",
            })
            return state

    result_summary = f"Total: {row_count} rows. First 5: {json.dumps(rows[:5], default=str)}"

    @llm_retry
    async def _call_llm(prompt: str):
        return await llm.ainvoke(prompt)

    base_prompt = EXPLAIN_PROMPT.format(
        user_query=state["user_query"],
        sql=state["generated_sql"],
        result_summary=result_summary,
    )
    response = await _call_llm(base_prompt)
    explanation = response.content.strip()

    # Backstop (prompt 5.1): the prompt does the main work; here we catch any
    # editorializing it let through. Detect world-claims, REGENERATE ONCE with a
    # stricter instruction quoting the violation, then fall back to a strictly
    # descriptive deterministic rendering. One retry max — latency stays bounded.
    verdict = is_overstated(explanation, state["user_query"])
    if verdict.overstated:
        triggers_str = ", ".join(sorted({phrase for _, phrase in verdict.triggers}))
        logger.info(
            "Explanation overstated (triggers: %s) — regenerating once "
            "(session=%s)",
            triggers_str, state.get("session_id", "unknown")[:8],
        )
        response = await _call_llm(base_prompt + STRICT_SUFFIX.format(triggers=triggers_str))
        explanation = response.content.strip()

        if is_overstated(explanation, state["user_query"]).overstated:
            logger.info(
                "Explanation still overstated after retry — using deterministic "
                "description (session=%s)",
                state.get("session_id", "unknown")[:8],
            )
            explanation = describe_result_plainly(
                rows, result.get("columns", []), row_count, state["user_query"]
            )

    state["explanation"] = explanation

    validation = state.get("validation_result") or {}
    quality = state.get("result_quality") or {}
    state["confidence_score"] = compute_confidence_score(
        correction_attempts=state["correction_attempts"],
        result_quality_status=quality.get("status", "GOOD"),
        syntax_warnings=validation.get("warnings", []),
        served_from_cache=state.get("served_from_cache", False),
        cache_similarity=state.get("cache_result", {}).get("similarity", 0.0) if state.get("cache_result") else 0.0,
    )

    if state["correction_attempts"] == 0 and quality.get("status") == "GOOD":
        try:
            stored = await store_fewshot_example(
                natural_language=state["user_query"],
                sql_query=state["generated_sql"],
                tables_used=state.get("tables_identified", []),
                auto_learned=True,
            )
            if not stored:
                logger.debug("Few-shot skipped (near-duplicate detected)")
        except Exception as e:
            logger.warning(
                "Non-critical write failed in explain_result "
                "(session=%s): %s: %s",
                state.get("session_id", "unknown")[:8], type(e).__name__, e,
            )

    if quality.get("status") == "GOOD" and result:
        try:
            embedding = await embed_text(state["user_query"])
            await store_cache_entry(
                user_query=state["user_query"],
                query_embedding=embedding,
                generated_sql=state["generated_sql"],
                result_preview=rows[:5],
                row_count=row_count,
                execution_time_ms=result.get("execution_time_ms", 0),
                chart_type=state.get("chart_config", {}).get("chart_type"),
                explanation=state["explanation"],
            )
        except Exception as e:
            logger.warning(
                "Non-critical write failed in explain_result "
                "(session=%s): %s: %s",
                state.get("session_id", "unknown")[:8], type(e).__name__, e,
            )

    state["is_complete"] = True
    state["completed_nodes"].append("explain_result")
    state["stream_updates"].append({
        "timestamp": now(), "node": "explain_result",
        "message": f"Complete — confidence: {state['confidence_score']:.0%} | corrections: {state['correction_attempts']}/3",
        "status": "done",
    })
    return state
