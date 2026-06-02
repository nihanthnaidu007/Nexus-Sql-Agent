"""Single configuration source for NIXUS SQL (introduced in 1.1e).

This object centralizes environment reads that were previously scattered as
ad-hoc ``os.environ`` / ``os.getenv`` calls across the core and the API
adapter. Every field default, type, and parsing tolerance mirrors the
pre-consolidation behavior EXACTLY as of 1.1e — this is a *consolidation*, not
a *hardening*. No default was added, dropped, or tightened, and no validation
was introduced that would reject a value the old loose code accepted.

Defaults reflect the raw reads:
  - ``os.environ.get("X")``        -> Optional field defaulting to ``None``.
  - ``os.environ.get("X", "v")``   -> field defaulting to ``"v"`` (cast to the
                                      type the old call site cast to).
  - The single effectively-required value (``DATABASE_URL``) is mirrored as a
    raw ``Optional[str]`` here; its required-ness is enforced exactly as before
    by ``nixus.db.connection``'s own ``RuntimeError`` guard, which is preserved.

Intentionally NOT folded in (adapter-process-local, not shared app config):
  - the Streamlit UI's ``API_BASE_URL`` (ui/app.py),
  - the eval harness's ``NIXUS_API_URL`` / ``NIXUS_METRICS_FILE`` (eval/conftest.py),
  - the retired Chinook migration script's vars (scripts/migrate_chinook.py).
See the 1.1e report for the rationale.
"""
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read from the process environment and from a .env file if present, matching
    # the project's existing python-dotenv (`load_dotenv()`) behavior. `extra`
    # is ignored so the many .env keys that are not modeled here (LANGCHAIN_*,
    # CHINOOK_*, API_BASE_URL, ...) do not raise. case_sensitive=False keeps the
    # uppercase env names matching the lowercase field names, as os.environ did.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Database ────────────────────────────────────────────────────────────
    # Old: db.connection -> os.environ.get("DATABASE_URL") (None), then raises
    # RuntimeError if falsy. graph.graph -> os.environ.get("DATABASE_URL", "").
    # Field mirrors the bare read (None); the ""-defaulting site applies `or ""`.
    database_url: Optional[str] = Field(default=None)

    # ── LLM API keys ────────────────────────────────────────────────────────
    # Reads varied across sites: .get("ANTHROPIC_API_KEY") -> None and
    # .get("ANTHROPIC_API_KEY", "") -> "". Field mirrors the bare read (None);
    # the two ""-defaulting sites apply `or ""` to stay byte-identical.
    anthropic_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)

    # ── Retrieval / correction tuning (int/float casts mirrored into the type) ─
    max_correction_attempts: int = Field(default=3)        # MAX_CORRECTION_ATTEMPTS
    schema_retrieval_top_k: int = Field(default=6)         # SCHEMA_RETRIEVAL_TOP_K
    fewshot_retrieval_top_k: int = Field(default=3)        # FEWSHOT_RETRIEVAL_TOP_K
    fewshot_similarity_threshold: float = Field(default=0.60)   # FEWSHOT_SIMILARITY_THRESHOLD
    cache_similarity_threshold: float = Field(default=0.92)     # CACHE_SIMILARITY_THRESHOLD
    query_timeout_ms: int = Field(default=30000)           # QUERY_TIMEOUT_MS
    pie_max_slices: int = Field(default=6)                 # PIE_MAX_SLICES

    # ── Cache eviction (read at API startup) ────────────────────────────────
    cache_max_age_days: int = Field(default=30)            # CACHE_MAX_AGE_DAYS
    cache_max_entries: int = Field(default=10000)          # CACHE_MAX_ENTRIES

    # ── API: CORS + health ──────────────────────────────────────────────────
    # Old read a raw string and split on "," with strip + empty-filter applied
    # at the call site. Kept as a raw string here so the call site can apply the
    # exact same split; a Pydantic list field would coerce commas differently
    # (and reject some previously-accepted input). future: could be a typed list.
    allowed_origins: str = Field(default="http://localhost:8501,http://localhost:3000")
    llm_health_cache_ttl: int = Field(default=300)         # LLM_HEALTH_CACHE_TTL

    # ── Logging ─────────────────────────────────────────────────────────────
    # Old applied .upper(); the call site keeps .upper() to stay identical.
    log_level: str = Field(default="INFO")                 # LOG_LEVEL

    # ── LangSmith observability ─────────────────────────────────────────────
    # Old truthiness was strictly `.lower() == "true"`, which is STRICTER than
    # Pydantic's bool coercion (which would treat "1"/"yes"/"on"/"t" as True).
    # To preserve exact behavior we keep the raw string and expose
    # `tracing_enabled` replicating the old test. Do NOT change this to a bool
    # field — that would accept inputs the old code treated as False.
    langchain_tracing_v2: str = Field(default="false")     # LANGCHAIN_TRACING_V2
    langchain_project: str = Field(default="nixus-sql")    # LANGCHAIN_PROJECT

    @property
    def tracing_enabled(self) -> bool:
        """Mirror of `os.environ.get("LANGCHAIN_TRACING_V2","false").lower()=="true"`."""
        return self.langchain_tracing_v2.lower() == "true"


# Single module-level instance imported by every call site. Reads the
# environment once at import, matching the project's prior import-time reads.
settings = Settings()
