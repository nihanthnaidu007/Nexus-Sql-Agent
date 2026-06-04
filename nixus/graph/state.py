from typing import TypedDict, Optional
from pydantic import BaseModel


class SchemaTable(BaseModel):
    table_name: str
    description: str
    columns_json: str
    sample_values_json: Optional[str]
    relevance_score: float


class FewShotExample(BaseModel):
    natural_language: str
    sql_query: str
    tables_used: list
    query_type: str
    similarity_score: float


class CacheResult(BaseModel):
    hit: bool
    similarity: float
    cached_sql: Optional[str] = None
    result_preview: Optional[list] = None
    chart_type: Optional[str] = None
    explanation: Optional[str] = None
    cache_id: Optional[int] = None


class ValidationResult(BaseModel):
    is_valid: bool
    errors: list
    warnings: list
    normalized_sql: str


class ExecutionResult(BaseModel):
    success: bool
    rows: list
    columns: list
    row_count: int
    execution_time_ms: float
    error: Optional[str] = None


class ResultQuality(BaseModel):
    status: str
    reasoning: str
    is_acceptable: bool


class CorrectionRecord(BaseModel):
    attempt: int
    failed_sql: str
    error_message: str
    fix_reasoning: str
    corrected_sql: str


class ChartConfig(BaseModel):
    chart_type: str
    x_column: Optional[str] = None
    y_column: Optional[str] = None
    color_column: Optional[str] = None
    title: str
    reasoning: str
    plotly_json: Optional[str] = None


class StreamUpdate(BaseModel):
    timestamp: str
    node: str
    message: str
    status: str


class SQLAgentState(TypedDict):
    user_query: str
    session_id: str
    # Stateless clarification round-trip inputs (Option B): carried in with the
    # request, not persisted server-side. Absent/0 for a normal single-turn query.
    clarification_context: Optional[dict]
    clarification_round: int
    scope_category: Optional[str]
    scope_message: Optional[str]
    # Response-outcome discriminator + the text the client surfaces for each.
    outcome: Optional[str]
    clarifying_question: Optional[str]
    reason: Optional[str]
    intent_class: str
    extracted_entities: list
    cache_result: Optional[dict]
    served_from_cache: bool
    relevant_schemas: list
    schema_context: str
    tables_identified: list
    similar_examples: list
    fewshot_context: str
    generated_sql: str
    validation_result: Optional[dict]
    grounding_result: Optional[dict]
    execution_result: Optional[dict]
    result_quality: Optional[dict]
    correction_attempts: int
    correction_history: list
    chart_config: Optional[dict]
    explanation: str
    confidence_score: float
    # Categorical confidence (5.2): the verdict plus its legible reasoning, so the
    # API/UI can show WHY confidence is what it is rather than a bare number.
    confidence: Optional[str]
    confidence_reasons: list
    confidence_signals: dict
    current_node: str
    completed_nodes: list
    is_complete: bool
    trace_id: Optional[str]
    trace_url: Optional[str]
    error: Optional[str]
    stream_updates: list
