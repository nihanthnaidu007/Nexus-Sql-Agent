from nixus.config import settings
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from nixus.graph.state import SQLAgentState

load_dotenv()

MAX_ATTEMPTS = settings.max_correction_attempts

from nixus.graph.nodes.parse_intent import parse_intent_node
from nixus.graph.nodes.check_cache import check_cache_node
from nixus.graph.nodes.retrieve_schema import retrieve_schema_node
from nixus.graph.nodes.retrieve_fewshot import retrieve_fewshot_node
from nixus.graph.nodes.generate_sql import generate_sql_node
from nixus.graph.nodes.validate_syntax import validate_syntax_node
from nixus.graph.nodes.execute_query import execute_query_node
from nixus.graph.nodes.check_result import check_result_node
from nixus.graph.nodes.self_correct import self_correct_node
from nixus.graph.nodes.classify_chart import classify_chart_node
from nixus.graph.nodes.explain_result import explain_result_node
from nixus.safety.approval_gate import safety_check_node

# LangGraph's AsyncPostgresSaver uses psycopg3 (not asyncpg) and requires
# the DATABASE_URL in plain `postgresql://` form. Strip any SQLAlchemy driver
# suffix so it works regardless of how DATABASE_URL was configured.
_pg_url = (
    (settings.database_url or "")
    .replace("postgresql+asyncpg://", "postgresql://")
    .replace("postgresql+psycopg2://", "postgresql://")
    .replace("postgres://", "postgresql://", 1)
)

# These three module-level singletons are created lazily inside the running
# event loop (FastAPI lifespan startup). AsyncPostgresSaver.__init__ calls
# asyncio.get_running_loop(), so it cannot be constructed at module-load time.
#
# The same AsyncPostgresSaver instance must be reused by both the initial
# invoke and any resume invoke (required for interrupt/resume to work across
# calls and across multiple API processes hitting the same Postgres).
_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None
_graph = None


async def init_checkpointer() -> None:
    """Open the checkpoint pool, instantiate the saver inside the running
    event loop, and create the `checkpoints` / `checkpoint_writes` /
    `checkpoint_blobs` tables if they don't exist. Idempotent.

    Must be called once during FastAPI lifespan startup BEFORE the graph is
    first invoked or built.
    """
    global _pool, _checkpointer
    if _checkpointer is not None:
        return
    _pool = AsyncConnectionPool(
        _pg_url,
        min_size=1,
        max_size=5,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()


async def aclose_checkpointer() -> None:
    """Close the checkpoint connection pool. Called from FastAPI lifespan shutdown."""
    global _pool, _checkpointer, _graph
    if _pool is not None:
        await _pool.close()
    _pool = None
    _checkpointer = None
    _graph = None


def build_graph():
    global _graph
    if _graph is not None:
        return _graph
    if _checkpointer is None:
        raise RuntimeError(
            "Checkpointer not initialized. Call `await init_checkpointer()` "
            "during FastAPI lifespan startup before building the graph."
        )

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

    _graph = workflow.compile(checkpointer=_checkpointer, interrupt_before=["safety_check"])
    return _graph
