import os
import logging
from dotenv import load_dotenv
from datetime import datetime
from langchain_anthropic import ChatAnthropic
from graph.state import SQLAgentState
from utils.retry import llm_retry
from utils.sql_safety import is_read_only_sql
from safety.approval_gate import contains_write_operation

load_dotenv()

logger = logging.getLogger(__name__)

GENERATE_SQL_SYSTEM_PROMPT = """You are an expert PostgreSQL query writer for the Chinook music database.

DATABASE SCHEMA (semantically retrieved — only relevant tables shown):
{schema_context}

FEW-SHOT EXAMPLES (similar past queries with verified correct SQL — follow these patterns):
{fewshot_context}

STRICT OUTPUT RULES:
1. Output ONLY the raw SQL query. No markdown. No backticks. No explanations.
2. Use ONLY tables and columns present in the schema above.
3. ALL table and column names MUST be double-quoted because they use PascalCase in PostgreSQL (e.g., "Artist", "ArtistId", "Track", "TrackId", "InvoiceLine", "MediaType"). Never reference them without double quotes.
4. Always alias tables in multi-table queries using the alias WITHOUT quotes (e.g., ar."ArtistId", t."TrackId").
5. Use ILIKE for case-insensitive text matching.
6. PostgreSQL date math: NOW() - INTERVAL '30 days', DATE_TRUNC('month', col), etc.
7. Always add LIMIT 1000 unless the user specifies a limit or asks for ALL records.
8. Qualify all ambiguous column names with table aliases.
9. NEVER reference a table not explicitly shown in the DATABASE SCHEMA section above.
10. For JOINs, verify the foreign key column exists in BOTH tables before writing the join.
11. If the question cannot be answered from the provided schema alone: output exactly CANNOT_ANSWER

User question: {user_query}
Intent: {intent_class}
Key entities: {entities}"""


def now():
    return datetime.now().strftime("%H:%M:%S")


async def generate_sql_node(state: SQLAgentState) -> SQLAgentState:
    state["current_node"] = "generate_sql"
    llm = ChatAnthropic(
        model="claude-sonnet-4-5",
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        temperature=0.1,
        max_tokens=1024,
    )

    prompt = GENERATE_SQL_SYSTEM_PROMPT.format(
        schema_context=state["schema_context"],
        fewshot_context=state["fewshot_context"],
        user_query=state["user_query"],
        intent_class=state["intent_class"],
        entities=", ".join(state["extracted_entities"]),
    )

    @llm_retry
    async def _call_llm(prompt_text: str):
        return await llm.ainvoke(prompt_text)

    response = await _call_llm(prompt)
    sql = response.content.strip()

    # Defense-in-depth #1: sqlglot AST parse. Catches structurally-parsed
    # WRITE statements that slipped past the LLM-based intent classifier.
    is_safe, reason = is_read_only_sql(sql)
    if not is_safe:
        logger.warning(
            "generate_sql: sqlglot blocked WRITE/non-SELECT statement (%s) for query: %r",
            reason, state.get("user_query", ""),
        )
        state["generated_sql"] = ""
        state["error"] = "Generated SQL contained a blocked statement type. Possible prompt injection detected."
        state["is_complete"] = True
        state["completed_nodes"].append("generate_sql")
        state["stream_updates"].append({
            "timestamp": now(), "node": "generate_sql",
            "message": f"Blocked non-SELECT SQL (sqlglot): {reason}",
            "status": "error",
        })
        return state

    # Defense-in-depth #2: regex scan. Catches obfuscated / unparseable
    # WRITE statements that the AST parser may have classified as SELECT.
    has_write, matched = contains_write_operation(sql)
    if has_write:
        logger.warning(
            "generate_sql: regex blocked WRITE statement (matched %r) for query: %r",
            matched, state.get("user_query", ""),
        )
        state["generated_sql"] = ""
        state["error"] = "Generated SQL contained a blocked statement type. Possible prompt injection detected."
        state["is_complete"] = True
        state["completed_nodes"].append("generate_sql")
        state["stream_updates"].append({
            "timestamp": now(), "node": "generate_sql",
            "message": f"Blocked write SQL (regex): {matched}",
            "status": "error",
        })
        return state

    state["generated_sql"] = sql
    state["completed_nodes"].append("generate_sql")
    state["stream_updates"].append({
        "timestamp": now(), "node": "generate_sql",
        "message": f"SQL generated — {len(sql.split())} tokens, attempt {state['correction_attempts'] + 1}/3",
        "status": "done",
    })
    return state
