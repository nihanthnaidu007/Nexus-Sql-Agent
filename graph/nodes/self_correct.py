import json
import os
from dotenv import load_dotenv
from datetime import datetime
from langchain_anthropic import ChatAnthropic
from graph.state import SQLAgentState

load_dotenv()

SELF_CORRECT_PROMPT = """You are a PostgreSQL debugging expert. A SQL query failed or returned bad results.
Reason about WHY it failed, then write a corrected version.

ORIGINAL QUESTION: {user_query}

DATABASE SCHEMA:
{schema_context}

CRITICAL REMINDER: ALL table and column names use PascalCase and MUST be double-quoted in PostgreSQL.
Correct: "Artist", "ArtistId", "Track", "TrackId", "InvoiceLine", "PlaylistTrack", "MediaType"
Wrong:   Artist, artist, ArtistId, Track, track, TrackId (any unquoted form)

FAILED SQL (attempt {attempt}):
{failed_sql}

FAILURE REASON:
{failure_reason}

ALL PRIOR ATTEMPTS:
{correction_history}

Respond ONLY with this JSON. No markdown, no backticks:
{{
    "fix_reasoning": "Your 1-2 sentence diagnosis of exactly why it failed and what you changed",
    "corrected_sql": "SELECT ... the fixed SQL here"
}}"""


def now():
    return datetime.now().strftime("%H:%M:%S")


async def self_correct_node(state: SQLAgentState) -> SQLAgentState:
    state["current_node"] = "self_correct"
    llm = ChatAnthropic(
        model="claude-sonnet-4-5",
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        temperature=0.1,
        max_tokens=1024,
    )

    state["correction_attempts"] += 1

    if state.get("execution_result") and not state["execution_result"]["success"]:
        failure_reason = f"EXECUTION ERROR: {state['execution_result']['error']}"
    elif state.get("result_quality") and not state["result_quality"]["is_acceptable"]:
        q = state["result_quality"]
        failure_reason = f"RESULT QUALITY ({q['status']}): {q['reasoning']}"
    elif state.get("validation_result") and not state["validation_result"]["is_valid"]:
        failure_reason = f"SYNTAX ERROR: {'; '.join(state['validation_result']['errors'])}"
    else:
        failure_reason = "Unknown failure"

    history_lines = [
        f"Attempt {r['attempt']}: ...{r['failed_sql'][-100:]} → {r['error_message'][:80]}"
        for r in state.get("correction_history", [])
    ] or ["None — first correction attempt"]

    prompt = SELF_CORRECT_PROMPT.format(
        user_query=state["user_query"],
        schema_context=state["schema_context"],
        failed_sql=state["generated_sql"],
        attempt=state["correction_attempts"],
        failure_reason=failure_reason,
        correction_history="\n".join(history_lines),
    )

    response = await llm.ainvoke(prompt)
    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"fix_reasoning": "LLM returned non-JSON response", "corrected_sql": state["generated_sql"]}

    state["correction_history"].append({
        "attempt": state["correction_attempts"],
        "failed_sql": state["generated_sql"],
        "error_message": failure_reason,
        "fix_reasoning": result["fix_reasoning"],
        "corrected_sql": result["corrected_sql"],
    })

    state["generated_sql"] = result["corrected_sql"]
    state["sql_history"].append(result["corrected_sql"])
    state["completed_nodes"].append("self_correct")
    state["stream_updates"].append({
        "timestamp": now(), "node": "self_correct",
        "message": f"Correction {state['correction_attempts']}/3 — {result['fix_reasoning'][:100]}",
        "status": "running",
    })
    return state
