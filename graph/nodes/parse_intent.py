import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel
from typing import Optional
from graph.state import SQLAgentState

llm = ChatAnthropic(
    model="claude-haiku-4-5",
    anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    temperature=0.1,
    max_tokens=512,
)


class IntentResult(BaseModel):
    intent_class: str
    extracted_entities: list
    write_operation_type: Optional[str] = None
    reasoning: str


PARSE_PROMPT = """Classify this natural language database query.

intent_class options:
- READ: wants to SELECT / retrieve data
- WRITE: wants to INSERT, UPDATE, DELETE, or DROP data
- SCHEMA_QUESTION: asking about table structure, column names
- AMBIGUOUS: unclear intent

extracted_entities: key concepts mentioned — table hints, filters, aggregations, time ranges, column hints.

Query: {user_query}

Respond ONLY with valid JSON matching this schema. No markdown, no backticks:
{{
  "intent_class": "READ|WRITE|SCHEMA_QUESTION|AMBIGUOUS",
  "extracted_entities": ["entity1", "entity2"],
  "write_operation_type": null,
  "reasoning": "one sentence"
}}"""


def now():
    return datetime.now().strftime("%H:%M:%S")


async def parse_intent_node(state: SQLAgentState) -> SQLAgentState:
    state["current_node"] = "parse_intent"
    structured_llm = llm.with_structured_output(IntentResult)
    result = await structured_llm.ainvoke(PARSE_PROMPT.format(user_query=state["user_query"]))

    state["intent_class"] = result.intent_class
    state["extracted_entities"] = result.extracted_entities
    state["write_operation_type"] = result.write_operation_type
    state["requires_approval"] = result.intent_class == "WRITE"
    state["completed_nodes"].append("parse_intent")
    state["stream_updates"].append({
        "timestamp": now(), "node": "parse_intent",
        "message": f"Intent: {result.intent_class} | Entities: {result.extracted_entities}",
        "status": "done",
    })
    return state
