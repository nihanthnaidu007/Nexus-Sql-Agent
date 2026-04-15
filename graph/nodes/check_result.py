from datetime import datetime
from graph.state import SQLAgentState

ROW_FETCH_LIMIT = 1000


def now():
    return datetime.now().strftime("%H:%M:%S")


async def check_result_node(state: SQLAgentState) -> SQLAgentState:
    state["current_node"] = "check_result"
    result = state["execution_result"]

    if not result["success"]:
        quality = {"status": "ERROR", "reasoning": result["error"], "is_acceptable": False}
    elif result["row_count"] == 0:
        quality = {
            "status": "EMPTY",
            "reasoning": "Zero rows returned. Likely causes: overly restrictive WHERE, wrong JOIN condition, or data doesn't exist.",
            "is_acceptable": False,
        }
    elif result["row_count"] >= ROW_FETCH_LIMIT:
        quality = {
            "status": "OVERFLOW",
            "reasoning": (
                "Query returned the maximum row limit (1000). "
                "Results may be incomplete. Consider adding "
                "a more specific filter or LIMIT clause."
            ),
            "is_acceptable": True,
        }
    else:
        quality = {"status": "GOOD", "reasoning": "Result looks valid.", "is_acceptable": True}

    state["result_quality"] = quality
    state["completed_nodes"].append("check_result")
    state["stream_updates"].append({
        "timestamp": now(), "node": "check_result",
        "message": f"Result quality: {quality['status']} — {result['row_count']} rows",
        "status": "done" if quality["is_acceptable"] else "error",
    })
    return state
