import os
import time
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from db.connection import engine
from graph.state import SQLAgentState

ROW_FETCH_LIMIT = 1000
QUERY_TIMEOUT_MS = int(os.environ.get("QUERY_TIMEOUT_MS", "30000"))


def now():
    return datetime.now().strftime("%H:%M:%S")


async def execute_query_node(state: SQLAgentState) -> SQLAgentState:
    state["current_node"] = "execute_query"
    sql = state["validation_result"]["normalized_sql"]
    start = time.monotonic()

    try:
        async with engine.connect() as conn:
            # Set statement timeout at the session level for this connection.
            # This is enforced by PostgreSQL itself, not by the driver.
            # If the query exceeds QUERY_TIMEOUT_MS, PostgreSQL cancels it
            # and raises a QueryCanceledError (surfacing through SQLAlchemy).
            # `SET LOCAL` only takes effect inside a transaction, so we wrap
            # the SET + the user SQL in a single begin() block.
            async with conn.begin():
                await conn.execute(
                    text(f"SET LOCAL statement_timeout = '{QUERY_TIMEOUT_MS}ms'")
                )
                result = await conn.execute(text(sql))
                rows = [dict(row._mapping) for row in result.fetchmany(ROW_FETCH_LIMIT)]
                columns = list(result.keys())
            elapsed = (time.monotonic() - start) * 1000

            state["execution_result"] = {
                "success": True,
                "rows": rows,
                "columns": columns,
                "row_count": len(rows),
                "execution_time_ms": round(elapsed, 1),
                "error": None,
            }
            state["stream_updates"].append({
                "timestamp": now(), "node": "execute_query",
                "message": f"Executed in {elapsed:.0f}ms — {len(rows)} rows returned",
                "status": "done",
            })
    except SQLAlchemyError as e:
        elapsed = (time.monotonic() - start) * 1000
        error_msg = str(e)
        if "statement timeout" in error_msg.lower() or "canceling statement" in error_msg.lower():
            error_msg = f"Query exceeded {QUERY_TIMEOUT_MS}ms timeout. Try a more specific query."
        state["execution_result"] = {
            "success": False,
            "rows": [],
            "columns": [],
            "row_count": 0,
            "execution_time_ms": round(elapsed, 1),
            "error": error_msg,
        }
        state["stream_updates"].append({
            "timestamp": now(), "node": "execute_query",
            "message": f"Execution FAILED: {error_msg[:150]}",
            "status": "error",
        })

    state["completed_nodes"].append("execute_query")
    return state
