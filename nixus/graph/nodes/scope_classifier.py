"""Graph-entry scope classifier (thin node over ``nixus.graph.scope``).

Decides, before any retrieval or generation, whether the user's input is an
in-scope data question (IN_SCOPE → continues into the existing flow), needs
clarification, is out of scope, or is a refused write request. The deterministic
fast-path (regex junk / clear write request) short-circuits without an LLM call;
everything else defers to a single small LLM classification biased toward
IN_SCOPE / NEEDS_CLARIFICATION.
"""
from nixus.config import settings
from dotenv import load_dotenv
from datetime import datetime
import logging

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from nixus.graph.state import SQLAgentState
from nixus.graph.scope import (
    ScopeCategory,
    ScopeResult,
    classify_scope,
    build_classifier_prompt,
    result_from_llm,
    OUT_OF_SCOPE_MESSAGE,
    CLARIFY_FALLBACK,
)
from nixus.utils.retry import llm_retry
from nixus.db.schema_store import list_schema_rows

load_dotenv()

logger = logging.getLogger(__name__)

llm = ChatAnthropic(
    model="claude-haiku-4-5",
    anthropic_api_key=(settings.anthropic_api_key or ""),
    temperature=0.0,
    max_tokens=256,
)


class ScopeClassification(BaseModel):
    category: str
    clarification: str = ""
    reason: str = ""


def now():
    return datetime.now().strftime("%H:%M:%S")


async def _schema_summary() -> str:
    """Cheap table-name list (no embedding call) so the classifier knows what
    'the data' is. Best-effort: a DB hiccup degrades to an empty summary, which
    the classifier handles by assuming a generic relational database."""
    try:
        rows = await list_schema_rows()
        if rows:
            return "Tables available: " + ", ".join(r["table_name"] for r in rows)
    except Exception as e:  # noqa: BLE001 — best-effort context only
        logger.debug("scope classifier schema summary unavailable: %s", e)
    return ""


async def classify_query(text: str, schema_context: str = "") -> ScopeResult:
    """Classify one user input. Deterministic fast-path first, else one LLM call.

    Fail-open: any LLM/parse failure returns IN_SCOPE so a transient error never
    turns a real question into a refusal.
    """
    deterministic = classify_scope(text)
    if deterministic is not None:
        return deterministic

    schema = schema_context or await _schema_summary()
    structured_llm = llm.with_structured_output(ScopeClassification)

    @llm_retry
    async def _call_llm(prompt: str):
        return await structured_llm.ainvoke(prompt)

    try:
        raw = await _call_llm(build_classifier_prompt(text, schema))
        return result_from_llm(raw.category, raw.clarification, raw.reason)
    except Exception as e:  # noqa: BLE001 — never refuse on a transient failure
        logger.warning("scope classifier LLM failed (%s) — defaulting IN_SCOPE", e)
        return ScopeResult(ScopeCategory.IN_SCOPE)


async def scope_classifier_node(state: SQLAgentState) -> SQLAgentState:
    state["current_node"] = "scope_classifier"
    text = state.get("user_query", "") or ""

    result = await classify_query(text, state.get("schema_context") or "")

    state["scope_category"] = result.category.value
    state["scope_message"] = result.clarification or result.reason or ""
    state["completed_nodes"].append("scope_classifier")
    state["stream_updates"].append({
        "timestamp": now(), "node": "scope_classifier",
        "message": f"Scope: {result.category.value}",
        "status": "done",
    })
    return state


async def scope_response_node(state: SQLAgentState) -> SQLAgentState:
    """Terminal for non-IN_SCOPE outcomes. Surfaces the clarification request or
    the refusal reason and completes the run. (4.2 turns NEEDS_CLARIFICATION into
    a full round-trip; here it is a single explanatory terminal.)"""
    state["current_node"] = "scope_response"
    category = state.get("scope_category", "")
    message = state.get("scope_message", "")

    if category == ScopeCategory.NEEDS_CLARIFICATION.value:
        state["explanation"] = message or CLARIFY_FALLBACK
        stream_status = "done"
    else:
        # OUT_OF_SCOPE or WRITE_REFUSAL — a definitive (non-fatal) refusal.
        refusal = message or OUT_OF_SCOPE_MESSAGE
        state["error"] = refusal
        state["explanation"] = refusal
        stream_status = "error"

    # Make the outcome visible on the intelligence strip (parse_intent never ran).
    state["intent_class"] = category or "OUT_OF_SCOPE"
    state["is_complete"] = True
    state["completed_nodes"].append("scope_response")
    state["stream_updates"].append({
        "timestamp": now(), "node": "scope_response",
        "message": state.get("explanation", ""),
        "status": stream_status,
    })
    return state
