import os
import time
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from db.connection import engine
from graph.state import SQLAgentState

ROW_FETCH_LIMIT = 1000


def now():
    return datetime.now().strftime("%H:%M:%S")


async def execute_query_node(state: SQLAgentState) -> SQLAgentState:
    state["current_node"] = "execute_query"
    sql = state["validation_result"]["normalized_sql"]
    timeout = int(os.environ.get("QUERY_EXECUTION_TIMEOUT_SECONDS", "10"))
    start = time.monotonic()

    try:
        async with engine.connect() as conn:
            timed_conn = await conn.execution_options(timeout=timeout)
            result = await timed_conn.execute(text(sql))
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
        state["execution_result"] = {
            "success": False,
            "rows": [],
            "columns": [],
            "row_count": 0,
            "execution_time_ms": round(elapsed, 1),
            "error": str(e),
        }
        state["stream_updates"].append({
            "timestamp": now(), "node": "execute_query",
            "message": f"Execution FAILED: {str(e)[:150]}",
            "status": "error",
        })

    state["completed_nodes"].append("execute_query")
    return state
