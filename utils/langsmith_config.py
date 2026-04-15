from dotenv import load_dotenv
load_dotenv()

import os
from langchain_core.runnables.config import RunnableConfig

TRACING_ENABLED = os.environ.get("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGSMITH_PROJECT = os.environ.get("LANGCHAIN_PROJECT", "nexus-sql")

# Cached at module level to avoid repeated API calls per request
_project_id_cache: str | None = None


def get_run_config(
    session_id: str,
    user_query: str,
    run_name: str = "nexus-sql-query"
) -> RunnableConfig:
    """
    Returns a RunnableConfig that attaches LangSmith metadata to a graph
    invocation. When LANGCHAIN_TRACING_V2=true, every LLM call and graph node
    is recorded with run_name, searchable tags, and structured metadata.
    """
    if not TRACING_ENABLED:
        return RunnableConfig(
            run_name=run_name,
            tags=["nexus-sql"],
            metadata={
                "session_id": session_id,
                "user_query": user_query[:100],
                "project": LANGSMITH_PROJECT
            }
        )

    return RunnableConfig(
        run_name=run_name,
        tags=[
            "nexus-sql",
            f"session:{session_id[:8]}",
        ],
        metadata={
            "session_id": session_id,
            "user_query": user_query[:100],
            "project": LANGSMITH_PROJECT,
            "version": "1.0.0"
        }
    )


async def get_trace_url(run_id: str) -> str | None:
    """
    Given a LangSmith run ID, returns the shareable trace URL.
    Constructs the URL locally using project metadata — does not wait
    for the run to finish uploading. ?poll=true lets LangSmith poll
    if the run isn't visible yet.
    Returns None if tracing is disabled or client init fails.
    """
    if not TRACING_ENABLED:
        return None
    try:
        global _project_id_cache
        from langsmith import Client
        client = Client()

        if _project_id_cache is None:
            project = client.read_project(project_name=LANGSMITH_PROJECT)
            _project_id_cache = str(project.id)

        host_url = client._host_url
        tenant_id = client._get_tenant_id()
        return (
            f"{host_url}/o/{tenant_id}/projects/p/"
            f"{_project_id_cache}/r/{run_id}?poll=true"
        )
    except Exception:
        return None


def is_tracing_enabled() -> bool:
    return TRACING_ENABLED
