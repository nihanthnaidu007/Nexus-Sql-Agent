from dotenv import load_dotenv
load_dotenv()

import uuid
import asyncio
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from langgraph.types import Command
from graph.graph import build_graph
from graph.state import SQLAgentState
from db.connection import check_db_connection
from db.query_cache import get_cache_stats
from db.fewshot_store import get_fewshot_stats
from utils.langsmith_config import get_run_config, get_trace_url, is_tracing_enabled

app = FastAPI(title="NEXUS SQL API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

graph = build_graph()


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
    """Merge a LangGraph thread_id into the run config so MemorySaver can find the checkpoint."""
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
        generated_sql="", sql_history=[],
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
    final_state = await graph.ainvoke(initial_state, config=config)
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
        "sql_history": [],
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

    async def event_generator():
        g = graph
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

                    # Build trace URL from root run ID
                    trace_url = None
                    if root_run_id and is_tracing_enabled():
                        trace_url = await get_trace_url(str(root_run_id))

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

                    yield {"event": "complete", "data": json.dumps(final, default=str)}

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e), "is_complete": True})}

    return EventSourceResponse(event_generator())


@app.post("/api/run-sql")
async def run_edited_sql(req: RunSQLRequest):
    """Skips generation — validates and executes user-provided SQL directly."""
    from graph.nodes.validate_syntax import validate_syntax_node
    from graph.nodes.execute_query import execute_query_node
    from graph.nodes.check_result import check_result_node
    from graph.nodes.classify_chart import classify_chart_node

    mini_state = SQLAgentState(
        user_query="[user-edited SQL]", session_id=req.session_id or str(uuid.uuid4()),
        generated_sql=req.sql, sql_history=[req.sql], correction_attempts=0,
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
    if mini_state["validation_result"]["is_valid"]:
        mini_state = await execute_query_node(mini_state)
        mini_state = await check_result_node(mini_state)
        mini_state = await classify_chart_node(mini_state)
    return mini_state


@app.get("/api/health")
async def health():
    db_ok = await check_db_connection()

    embedding_ok = False
    try:
        from utils.embeddings import embed_text
        test = embed_text("health check")
        embedding_ok = len(test) == 1536
    except Exception:
        embedding_ok = False

    llm_ok = False
    try:
        import os
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(
            model="claude-haiku-4-5",
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            max_tokens=10
        )
        resp = await llm.ainvoke("ping")
        llm_ok = len(resp.content) > 0
    except Exception:
        llm_ok = False

    return {
        "status": "ok" if (db_ok and embedding_ok) else "degraded",
        "db_connected": db_ok,
        "embedding_api": embedding_ok,
        "llm_api": llm_ok,
        "langsmith_tracing": is_tracing_enabled(),
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
    g = graph
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


@app.get("/api/fewshot-stats")
async def fewshot_stats():
    return await get_fewshot_stats()
