import json
import logging
from dotenv import load_dotenv
from datetime import datetime
from langchain_anthropic import ChatAnthropic

load_dotenv()

from db.fewshot_store import store_fewshot_example
from db.query_cache import store_cache_entry
from utils.embeddings import embed_text
from utils.confidence import compute_confidence_score
from utils.retry import llm_retry
from graph.state import SQLAgentState

logger = logging.getLogger(__name__)

EXPLAIN_PROMPT = """You are explaining a SQL query result to a business user. Be direct and specific.

Original question: {user_query}
SQL used: {sql}
Result: {result_summary}
Correction attempts needed: {attempts}

Write 2-3 sentences. Rules:
- Open with the direct answer using specific numbers from the data.
- Add one key insight if the data reveals something interesting.
- Never mention SQL, tables, columns, or technical terms.
- Never say "the query returned" or "the data shows".
- Write as if you already knew the answer and are confirming it."""


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

    response = await _call_llm(EXPLAIN_PROMPT.format(
        user_query=state["user_query"],
        sql=state["generated_sql"],
        result_summary=result_summary,
        attempts=state["correction_attempts"],
    ))
    state["explanation"] = response.content.strip()

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
