from dotenv import load_dotenv
load_dotenv()

import os
import uuid
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from langgraph.types import Command
from graph.graph import build_graph, init_checkpointer, aclose_checkpointer
from graph.state import SQLAgentState
from db.connection import check_db_connection
from db.query_cache import get_cache_stats, evict_stale_cache_entries
from db.fewshot_store import get_fewshot_stats
from utils.langsmith_config import get_run_config, get_trace_url, is_tracing_enabled
from utils.sql_safety import is_read_only_sql
from utils.logging_config import log_query_start, log_query_complete, log_node_event

logger = logging.getLogger("nexus_sql.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure pgvector + agent tables exist before serving (idempotent).

    Also opens the LangGraph PostgreSQL checkpoint pool, creates the
    `checkpoints` / `checkpoint_writes` / `checkpoint_blobs` tables on first
    run, and evicts stale `query_cache` entries.
    """
    from db.schema_init import init_database

    try:
        await asyncio.to_thread(init_database)
    except Exception:
        logger.exception("Database initialization failed; cache/few-shot endpoints may error until init succeeds")

    try:
        await init_checkpointer()
        build_graph()
        logger.info("LangGraph PostgreSQL checkpointer initialized and graph compiled.")
    except Exception:
        logger.exception("Checkpointer initialization failed; WRITE approval interrupt/resume will not work")

    try:
        eviction_stats = await evict_stale_cache_entries(
            max_age_days=int(os.environ.get("CACHE_MAX_AGE_DAYS", "30")),
            max_entries=int(os.environ.get("CACHE_MAX_ENTRIES", "10000")),
        )
        logger.info(f"Cache eviction on startup: {eviction_stats}")
    except Exception:
        logger.exception("Cache eviction on startup failed; continuing anyway")

    yield

    try:
        await aclose_checkpointer()
    except Exception:
        logger.exception("Failed to close checkpointer connection pool")


app = FastAPI(title="NEXUS SQL API", version="1.0.0", lifespan=lifespan)

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8501,http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch any uncaught exception from a non-streaming endpoint, log the
    full traceback server-side, and return a structured JSON error with a
    short trace_id the user can quote when reporting the failure.

    Note: this handler does NOT intercept errors that originate inside an
    in-flight SSE stream — by that point the response has already begun
    streaming, so Starlette routes the error through the EventSourceResponse
    generator. /api/stream already catches its own exceptions and yields a
    structured `{"event": "error", ...}` SSE event.
    """
    trace_id = str(uuid.uuid4())[:8]
    logger.error(
        f"[{trace_id}] Unhandled exception on {request.method} {request.url.path}: "
        f"{type(exc).__name__}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected error occurred.",
            "trace_id": trace_id,
            "type": type(exc).__name__,
        },
    )


class RunRequest(BaseModel):
    user_query: str
    session_id: str = ""


class RunSQLRequest(BaseModel):
    sql: str
    session_id: str = ""


class StreamRequest(BaseModel):
    user_query: str
    session_id: str = ""


class ApproveWriteRequest(BaseModel):
    session_id: str
    approved: bool


def get_thread_config(session_id: str, base_config: dict | None = None) -> dict:
    """Merge a LangGraph thread_id into the run config so the AsyncPostgresSaver checkpointer can find the checkpoint."""
    cfg = dict(base_config) if base_config else {}
    cfg["configurable"] = {**(cfg.get("configurable") or {}), "thread_id": session_id}
    return cfg


@app.post("/api/run")
async def run_agent(req: RunRequest):
    session_id = req.session_id or str(uuid.uuid4())
    initial_state = SQLAgentState(
        user_query=req.user_query,
        session_id=session_id,
        intent_class="", extracted_entities=[], requires_approval=False,
        write_operation_type=None, approval_granted=False,
        cache_result=None, served_from_cache=False,
        relevant_schemas=[], schema_context="", tables_identified=[],
        similar_examples=[], fewshot_context="",
        generated_sql="",
        validation_result=None, execution_result=None, result_quality=None,
        correction_attempts=0, correction_history=[],
        chart_config=None, explanation="", confidence_score=0.0,
        current_node="", completed_nodes=[], is_complete=False,
        trace_id=None, trace_url=None, error=None, stream_updates=[]
    )
    config = get_thread_config(session_id, get_run_config(
        session_id=session_id,
        user_query=req.user_query,
        run_name="nexus-sql-query"
    ))
    start = log_query_start(logger, session_id, req.user_query)
    final_state = await build_graph().ainvoke(initial_state, config=config)
    log_query_complete(
        logger,
        session_id=session_id,
        user_query=req.user_query,
        intent_class=final_state.get("intent_class", "unknown"),
        cache_hit=final_state.get("served_from_cache", False),
        corrections_used=final_state.get("correction_attempts", 0),
        result_quality=(final_state.get("result_quality") or {}).get("status", "unknown"),
        row_count=(final_state.get("execution_result") or {}).get("row_count", 0),
        chart_type=(final_state.get("chart_config") or {}).get("chart_type"),
        duration_ms=(time.monotonic() - start) * 1000,
        error=final_state.get("error"),
    )
    return final_state


@app.post("/api/stream")
async def stream_agent(req: StreamRequest):
    """
    SSE endpoint. Streams one event per node completion.
    Each event is a JSON-encoded partial state update.
    Final event has is_complete=True with full result and trace_url.
    """
    session_id = req.session_id or str(uuid.uuid4())

    initial_state = {
        "user_query": req.user_query,
        "session_id": session_id,
        "intent_class": "",
        "extracted_entities": [],
        "requires_approval": False,
        "write_operation_type": None,
        "approval_granted": False,
        "cache_result": None,
        "served_from_cache": False,
        "relevant_schemas": [],
        "schema_context": "",
        "tables_identified": [],
        "similar_examples": [],
        "fewshot_context": "",
        "generated_sql": "",
        "validation_result": None,
        "execution_result": None,
        "result_quality": None,
        "correction_attempts": 0,
        "correction_history": [],
        "chart_config": None,
        "explanation": "",
        "confidence_score": 0.0,
        "current_node": "",
        "completed_nodes": [],
        "is_complete": False,
        "trace_id": None,
        "trace_url": None,
        "error": None,
        "stream_updates": []
    }

    config = get_thread_config(session_id, get_run_config(
        session_id=session_id,
        user_query=req.user_query,
        run_name="nexus-sql-stream"
    ))

    stream_start = log_query_start(logger, session_id, req.user_query)

    async def event_generator():
        g = build_graph()
        last_update_count = 0
        root_run_id = None   # run_id of the root chain (set on first on_chain_start)

        NODE_NAMES = {
            "parse_intent", "safety_check", "check_cache", "retrieve_schema",
            "retrieve_fewshot", "generate_sql", "validate_syntax", "execute_query",
            "check_result", "self_correct", "classify_chart", "explain_result"
        }

        try:
            async for event in g.astream_events(initial_state, config=config, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")
                run_id = event.get("run_id", "")

                # Capture the root chain run_id from the very first chain start.
                # This is robust to whatever run_name the config assigns the root.
                if kind == "on_chain_start" and root_run_id is None:
                    root_run_id = run_id

                if kind == "on_chain_end" and name in NODE_NAMES:
                    output = event.get("data", {}).get("output", {})
                    if not isinstance(output, dict):
                        continue

                    all_updates = output.get("stream_updates", [])
                    new_updates = all_updates[last_update_count:]
                    last_update_count = len(all_updates)

                    partial = {
                        "node": name,
                        "completed_nodes": output.get("completed_nodes", []),
                        "current_node": output.get("current_node", name),
                        "stream_updates": new_updates,
                        "intent_class": output.get("intent_class", ""),
                        "extracted_entities": output.get("extracted_entities", []),
                        "tables_identified": output.get("tables_identified", []),
                        "served_from_cache": output.get("served_from_cache", False),
                        "correction_attempts": output.get("correction_attempts", 0),
                        "confidence_score": output.get("confidence_score", 0.0),
                        "error": output.get("error"),
                        "is_complete": False
                    }

                    log_node_event(logger, session_id, name, "complete")
                    yield {"event": "node_complete", "data": json.dumps(partial)}
                    await asyncio.sleep(0)

                elif kind == "on_chain_end" and run_id == root_run_id:
                    # Root chain completed — send the final event regardless of
                    # what run_name the config assigned to the chain
                    output = event.get("data", {}).get("output", {})
                    if not isinstance(output, dict):
                        continue

                    # Detect interrupt: graph paused waiting for write approval
                    if (
                        output.get("requires_approval")
                        and "safety_check" not in output.get("completed_nodes", [])
                    ):
                        operation = output.get("write_operation_type") or "WRITE"
                        interrupted = {
                            "node": "interrupted",
                            "is_complete": False,
                            "requires_approval": True,
                            "write_operation_type": operation,
                            "session_id": session_id,
                            "stream_updates": output.get("stream_updates", []),
                            "completed_nodes": output.get("completed_nodes", []),
                        }
                        yield {"event": "interrupted", "data": json.dumps(interrupted)}
                        return

                    # Build trace URL from root run ID.
                    # get_trace_url is sync (uses time.sleep for retries);
                    # run it in a thread so we don't block the event loop.
                    trace_url = None
                    if root_run_id and is_tracing_enabled():
                        trace_url = await asyncio.to_thread(
                            get_trace_url, str(root_run_id)
                        )

                    final = {
                        "node": "complete",
                        "is_complete": True,
                        "intent_class": output.get("intent_class"),
                        "extracted_entities": output.get("extracted_entities", []),
                        "tables_identified": output.get("tables_identified", []),
                        "generated_sql": output.get("generated_sql"),
                        "validation_result": output.get("validation_result"),
                        "execution_result": output.get("execution_result"),
                        "result_quality": output.get("result_quality"),
                        "chart_config": output.get("chart_config"),
                        "explanation": output.get("explanation"),
                        "confidence_score": output.get("confidence_score", 0.0),
                        "correction_attempts": output.get("correction_attempts", 0),
                        "correction_history": output.get("correction_history", []),
                        "served_from_cache": output.get("served_from_cache", False),
                        "cache_result": output.get("cache_result"),
                        "similar_examples": output.get("similar_examples", []),
                        "stream_updates": output.get("stream_updates", []),
                        "completed_nodes": output.get("completed_nodes", []),
                        "error": output.get("error"),
                        "trace_id": str(root_run_id) if root_run_id else None,
                        "trace_url": trace_url,
                        "session_id": session_id
                    }

                    log_query_complete(
                        logger,
                        session_id=session_id,
                        user_query=req.user_query,
                        intent_class=output.get("intent_class", "unknown") or "unknown",
                        cache_hit=output.get("served_from_cache", False),
                        corrections_used=output.get("correction_attempts", 0),
                        result_quality=(output.get("result_quality") or {}).get("status", "unknown"),
                        row_count=(output.get("execution_result") or {}).get("row_count", 0),
                        chart_type=(output.get("chart_config") or {}).get("chart_type"),
                        duration_ms=(time.monotonic() - stream_start) * 1000,
                        error=output.get("error"),
                    )
                    yield {"event": "complete", "data": json.dumps(final, default=str)}

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e), "is_complete": True})}

    return EventSourceResponse(event_generator())


@app.post("/api/run-sql")
async def run_edited_sql(req: RunSQLRequest):
    """Skips generation — validates and executes user-provided SQL directly.

    Server-side guard: only SELECT (and WITH ... SELECT) statements are
    permitted. Any INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/COMMAND
    is rejected at the API boundary, regardless of caller (UI or curl).
    """
    is_safe, reason = is_read_only_sql(req.sql)
    if not is_safe:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Only SELECT statements are permitted.",
                "detail": reason,
            },
        )

    from graph.nodes.validate_syntax import validate_syntax_node
    from graph.nodes.execute_query import execute_query_node
    from graph.nodes.check_result import check_result_node
    from graph.nodes.classify_chart import classify_chart_node

    mini_state = SQLAgentState(
        user_query="[user-edited SQL]", session_id=req.session_id or str(uuid.uuid4()),
        generated_sql=req.sql, correction_attempts=0,
        correction_history=[], completed_nodes=[], stream_updates=[],
        intent_class="READ", extracted_entities=[], requires_approval=False,
        write_operation_type=None, approval_granted=True,
        cache_result=None, served_from_cache=False,
        relevant_schemas=[], schema_context="", tables_identified=[],
        similar_examples=[], fewshot_context="",
        validation_result=None, execution_result=None, result_quality=None,
        chart_config=None, explanation="", confidence_score=0.0,
        current_node="", is_complete=False,
        trace_id=None, trace_url=None, error=None
    )
    mini_state = await validate_syntax_node(mini_state)

    validation_result = mini_state.get("validation_result") or {}
    is_valid = validation_result.get("is_valid", False)
    # validate_syntax_node stores errors as a list under "errors"
    errors = validation_result.get("errors") or []
    error_message = errors[0] if errors else validation_result.get("error_message", "SQL validation failed.")

    if is_valid:
        mini_state = await execute_query_node(mini_state)
        mini_state = await check_result_node(mini_state)
        mini_state = await classify_chart_node(mini_state)
    else:
        if not mini_state.get("error"):
            mini_state["error"] = error_message

    return mini_state


# Module-level LLM connectivity cache — avoids burning tokens on every probe.
_llm_health_cache: dict = {"status": "unknown", "checked_at": 0.0}
LLM_HEALTH_CACHE_TTL = int(os.environ.get("LLM_HEALTH_CACHE_TTL", "300"))  # 5 minutes


async def _check_llm_connectivity() -> dict:
    """Check LLM API connectivity via token-free metadata calls.

    Results are cached for LLM_HEALTH_CACHE_TTL seconds so repeated
    health probes (e.g. Streamlit's 30-second polling) do not burn tokens.

    `anthropic.models.list()` and `openai.models.list()` are metadata-only
    endpoints — they do not invoke a model and have zero token cost.
    """
    now = time.monotonic()
    if now - _llm_health_cache["checked_at"] < LLM_HEALTH_CACHE_TTL:
        return _llm_health_cache.copy()

    anthropic_ok = False
    openai_ok = False

    try:
        import anthropic as _anthropic
        _anthropic.Anthropic().models.list(limit=1)
        anthropic_ok = True
    except Exception as e:
        logger.warning(f"Anthropic health check failed: {type(e).__name__}: {e}")

    try:
        from openai import AsyncOpenAI as _OAI
        await _OAI().models.list()
        openai_ok = True
    except Exception as e:
        logger.warning(f"OpenAI health check failed: {type(e).__name__}: {e}")

    _llm_health_cache.update({
        "anthropic_connected": anthropic_ok,
        "openai_connected": openai_ok,
        "status": "ok" if (anthropic_ok and openai_ok) else "degraded",
        "checked_at": now,
    })
    logger.info(
        f"LLM connectivity checked: anthropic={anthropic_ok} openai={openai_ok}"
    )
    return _llm_health_cache.copy()


@app.get("/api/health")
async def health():
    """Fast health check.

    DB connectivity: checked on every call (a single `SELECT 1`, ~1ms).
    LLM connectivity: checked at most once every LLM_HEALTH_CACHE_TTL seconds
    using token-free metadata API calls. This prevents Streamlit's 30-second
    polling from burning Anthropic/OpenAI quota.
    """
    db_ok = await check_db_connection()
    llm_health = await _check_llm_connectivity()

    overall = "ok" if (db_ok and llm_health["status"] == "ok") else "degraded"

    return {
        "status": overall,
        "db_connected": db_ok,
        "anthropic_connected": llm_health.get("anthropic_connected", False),
        "openai_connected": llm_health.get("openai_connected", False),
        "langsmith_tracing": is_tracing_enabled(),
        "llm_last_checked": llm_health.get("checked_at", 0),
        "nodes": [
            "parse_intent", "safety_check", "check_cache", "retrieve_schema", "retrieve_fewshot",
            "generate_sql", "validate_syntax", "execute_query", "check_result",
            "self_correct", "classify_chart", "explain_result"
        ],
        "version": "1.0.0"
    }


@app.post("/api/approve-write")
async def approve_write(req: ApproveWriteRequest):
    """Resume an interrupted graph with the human's approval decision."""
    g = build_graph()
    config = get_thread_config(req.session_id)
    final_state = await g.ainvoke(
        Command(update={"approval_granted": req.approved}, resume=req.approved),
        config=config,
    )
    return {
        "status": "approved" if req.approved else "denied",
        "approval_granted": req.approved,
        "explanation": final_state.get("explanation", ""),
        "error": final_state.get("error"),
        "generated_sql": final_state.get("generated_sql"),
        "execution_result": final_state.get("execution_result"),
        "chart_config": final_state.get("chart_config"),
        "confidence_score": final_state.get("confidence_score", 0.0),
        "completed_nodes": final_state.get("completed_nodes", []),
    }


@app.get("/api/cache-stats")
async def cache_stats():
    return await get_cache_stats()


@app.post("/api/cache-evict")
async def cache_evict(
    max_age_days: int = 30,
    max_entries: int = 10_000,
):
    """Manually trigger cache eviction. Intended for an admin or a scheduled
    job. TTL drops rows not accessed in `max_age_days`; LRU then caps the
    table size at `max_entries`."""
    stats = await evict_stale_cache_entries(
        max_age_days=max_age_days,
        max_entries=max_entries,
    )
    return {"status": "ok", "evicted": stats}


@app.get("/api/fewshot-stats")
async def fewshot_stats():
    return await get_fewshot_stats()
