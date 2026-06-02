import re
from datetime import datetime


# These patterns match the start of any SQL statement that modifies data or schema.
# They are intentionally conservative — false positives are safe, false negatives are not.
_WRITE_PATTERNS = re.compile(
    r"""
    ^\s*                        # optional leading whitespace
    (
        INSERT\s+INTO           |
        UPDATE\s+\w             |
        DELETE\s+FROM           |
        DROP\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW|FUNCTION|TRIGGER|SEQUENCE) |
        TRUNCATE\s+             |
        CREATE\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW|FUNCTION|TRIGGER|SEQUENCE) |
        ALTER\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW|FUNCTION|TRIGGER|SEQUENCE) |
        REPLACE\s+INTO          |
        MERGE\s+INTO            |
        CALL\s+\w               |
        EXECUTE\s+\w            |
        GRANT\s+                |
        REVOKE\s+
    )
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)


def contains_write_operation(sql: str) -> tuple[bool, str]:
    """
    Rule-based regex scan of SQL for any data-modifying or schema-modifying
    statement. This is a defense-in-depth check, not the primary safety gate.

    Returns:
        (True, matched_keyword) if a write operation is detected.
        (False, "") if no write operation is found.
    """
    match = _WRITE_PATTERNS.search(sql)
    if match:
        return True, match.group(0).strip()
    return False, ""


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
