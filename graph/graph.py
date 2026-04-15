import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from graph.state import SQLAgentState

load_dotenv()

MAX_ATTEMPTS = int(os.environ.get("MAX_CORRECTION_ATTEMPTS", "3"))

from graph.nodes.parse_intent import parse_intent_node
from graph.nodes.check_cache import check_cache_node
from graph.nodes.retrieve_schema import retrieve_schema_node
from graph.nodes.retrieve_fewshot import retrieve_fewshot_node
from graph.nodes.generate_sql import generate_sql_node
from graph.nodes.validate_syntax import validate_syntax_node
from graph.nodes.execute_query import execute_query_node
from graph.nodes.check_result import check_result_node
from graph.nodes.self_correct import self_correct_node
from graph.nodes.classify_chart import classify_chart_node
from graph.nodes.explain_result import explain_result_node
from safety.guardrails import safety_check_node

# Module-level singletons — created once so the same MemorySaver instance is
# used for both the initial invoke and any resume invoke (required for
# interrupt/resume to work across calls).
_memory = MemorySaver()
_graph = None


def build_graph():
    global _graph
    if _graph is not None:
        return _graph

    workflow = StateGraph(SQLAgentState)

    workflow.add_node("parse_intent",     parse_intent_node)
    workflow.add_node("safety_check",     safety_check_node)
    workflow.add_node("check_cache",      check_cache_node)
    workflow.add_node("retrieve_schema",  retrieve_schema_node)
    workflow.add_node("retrieve_fewshot", retrieve_fewshot_node)
    workflow.add_node("generate_sql",     generate_sql_node)
    workflow.add_node("validate_syntax",  validate_syntax_node)
    workflow.add_node("execute_query",    execute_query_node)
    workflow.add_node("check_result",     check_result_node)
    workflow.add_node("self_correct",     self_correct_node)
    workflow.add_node("classify_chart",   classify_chart_node)
    workflow.add_node("explain_result",   explain_result_node)

    workflow.set_entry_point("parse_intent")

    workflow.add_conditional_edges("parse_intent",
        lambda s: "safety_check" if s["requires_approval"] else "check_cache",
        {"safety_check": "safety_check", "check_cache": "check_cache"})

    workflow.add_conditional_edges("safety_check",
        lambda s: "check_cache" if s.get("approval_granted") else END,
        {"check_cache": "check_cache", END: END})

    workflow.add_conditional_edges("check_cache",
        lambda s: "classify_chart" if s["served_from_cache"] else "retrieve_schema",
        {"classify_chart": "classify_chart", "retrieve_schema": "retrieve_schema"})

    workflow.add_edge("retrieve_schema",  "retrieve_fewshot")
    workflow.add_edge("retrieve_fewshot", "generate_sql")
    workflow.add_edge("generate_sql",     "validate_syntax")

    workflow.add_conditional_edges("validate_syntax",
        lambda s: (
            "END" if s.get("error") and "cannot be answered" in (s.get("error") or "").lower()
            else (
                "execute_query" if s["validation_result"]["is_valid"]
                else ("self_correct" if s["correction_attempts"] < MAX_ATTEMPTS else "explain_result")
            )
        ),
        {"execute_query": "execute_query", "self_correct": "self_correct",
         "explain_result": "explain_result", "END": END})

    workflow.add_edge("execute_query", "check_result")

    workflow.add_conditional_edges("check_result",
        lambda s: (
            "classify_chart" if s["result_quality"]["is_acceptable"]
            else ("self_correct" if s["correction_attempts"] < MAX_ATTEMPTS else "explain_result")
        ),
        {"classify_chart": "classify_chart", "self_correct": "self_correct", "explain_result": "explain_result"})

    workflow.add_edge("self_correct",   "validate_syntax")
    workflow.add_edge("classify_chart", "explain_result")
    workflow.add_edge("explain_result", END)

    _graph = workflow.compile(checkpointer=_memory, interrupt_before=["safety_check"])
    return _graph


async def run_graph(initial_state: dict, config: dict) -> dict:
    """Run graph to completion or interrupt point."""
    g = build_graph()
    return await g.ainvoke(initial_state, config)
