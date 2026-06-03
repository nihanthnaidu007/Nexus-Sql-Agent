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

    # ── Database (split into two connections in 2.1) ────────────────────────
    # NIXUS now talks to TWO databases:
    #   - state_db  (READ-WRITE): NIXUS-owned bookkeeping — schema_embeddings,
    #     fewshot_examples, query_cache, schema_migrations, and the LangGraph
    #     checkpointer tables.
    #   - target_db (STRICTLY READ-ONLY): the user's data. The generated SQL is
    #     executed here through a Postgres role that holds only SELECT.
    #
    # ``STATE_DATABASE_URL`` is the canonical name; the historical
    # ``DATABASE_URL`` is still honored as a fallback so existing .env files keep
    # working. ``state_url`` resolves the two. Both default to None (the bare
    # read); ``nixus.db.connection`` enforces required-ness via its RuntimeError
    # guard, exactly as before.
    state_database_url: Optional[str] = Field(default=None)   # STATE_DATABASE_URL
    database_url: Optional[str] = Field(default=None)         # DATABASE_URL (legacy → state)

    # Read-only handle the APP uses for the target database. Never written to.
    target_database_url: Optional[str] = Field(default=None)  # TARGET_DATABASE_URL

    # Writable OWNER connection to the target database, used ONLY by the one-time
    # Chinook seed / provisioning scripts (never by the app at runtime). The app's
    # only handle to the target is the read-only ``target_database_url`` above.
    target_admin_database_url: Optional[str] = Field(default=None)  # TARGET_ADMIN_DATABASE_URL

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

    # ── Resolved DB URLs ────────────────────────────────────────────────────
    @property
    def state_url(self) -> Optional[str]:
        """The state (NIXUS-owned, read-write) DB URL.

        Prefers ``STATE_DATABASE_URL``; falls back to the legacy ``DATABASE_URL``
        so existing .env files keep working unchanged.
        """
        return self.state_database_url or self.database_url

    @property
    def target_url(self) -> Optional[str]:
        """The target (user data, READ-ONLY) DB URL used by the app."""
        return self.target_database_url

    @property
    def target_admin_url(self) -> Optional[str]:
        """Writable OWNER URL to the target DB — bootstrap/seed scripts only."""
        return self.target_admin_database_url


# Single module-level instance imported by every call site. Reads the
# environment once at import, matching the project's prior import-time reads.
settings = Settings()
