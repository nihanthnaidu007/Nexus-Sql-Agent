from datetime import datetime


def now():
    return datetime.now().strftime("%H:%M:%S")


async def safety_check_node(state) -> dict:
    state["current_node"] = "safety_check"
    operation = state.get("write_operation_type") or "WRITE"
    approved = state.get("approval_granted", False)

    if approved:
        state["stream_updates"].append({
            "timestamp": now(), "node": "safety_check",
            "message": f"{operation} operation approved",
            "status": "done",
        })
    else:
        state["approval_granted"] = False
        state["error"] = (
            f"⚠ {operation} operation blocked — "
            f"approval was denied or timed out."
        )
        state["stream_updates"].append({
            "timestamp": now(), "node": "safety_check",
            "message": f"{operation} operation denied",
            "status": "error",
        })

    state["completed_nodes"].append("safety_check")
    return state
