# NIXUS SQL — Architecture

This document describes the **actual current structure** of the codebase as of
Phase 1.1 (the core relocation), and the rules every later phase must obey. It
is descriptive, not aspirational: where today's reality differs from the target,
the gap is called out with the phase that closes it.

## Core principle

There is **one framework-agnostic core** (`nixus/`) and several **thin adapters**
around it (`api/`, `ui/`, and the future `cli/` and React `frontend/`). The core
contains all the logic for understanding a question, retrieving schema/examples,
generating and validating SQL, executing it, and explaining the result. It knows
nothing about HTTP, Streamlit, or any transport.

Why: the same query logic must be runnable from the FastAPI service today, from a
CLI (Phase 7), and from a React backend (Phase 8) without duplication. That only
holds if a single function can run a query end to end **without importing a web
framework**. That function is `nixus/services/query_service.py::run_query`.

## Actual module map (as it exists now)

```
nixus/                     the framework-agnostic core
├── config.py              single typed settings object (Pydantic BaseSettings); the one config source
├── utils/                 cross-cutting helpers: embeddings, retry, sql_safety, sql_formatter,
│                          confidence, logging_config, langsmith_config
├── db/                    all database access: connection (engines), schema_store, fewshot_store,
│                          query_cache, schema_init. The ONLY place raw SQL lives.
├── safety/               approval_gate: the safety_check node + write-operation detection
│                          (WRITE approval is slated to be cut in Phase 4)
├── graph/                 the LangGraph engine
│   ├── state.py           SQLAgentState (the TypedDict state shape)
│   ├── graph.py           build_graph(): node registration, routing/edges, compile with
│   │                      AsyncPostgresSaver checkpointer + interrupt_before=["safety_check"]
│   └── nodes/             the 12 nodes: parse_intent, check_cache, retrieve_schema,
│                          retrieve_fewshot, generate_sql, validate_syntax, execute_query,
│                          check_result, self_correct, classify_chart, explain_result
│                          (+ safety_check, which lives in safety/ but is registered here)
└── services/             the query entry point
    └── query_service.py   run_query(user_query, session_id) — THE function adapters call

api/                       FastAPI adapter (HTTP shell only): routes (all under /api/v1),
                           request/response models, SSE streaming, lifespan (checkpointer +
                           graph build), and context.py (RequestContext: per-request identity)
ui/                        Streamlit adapter (app.py)
eval/                      benchmark + behavioral tests (run_benchmark.py, test_*.py, conftest.py)
scripts/                   operational scripts: init_db, seed_*, migrate_chinook (Chinook retired in 2.4)
```

**Planned but not present yet** (do not pretend these exist):
- `nixus/schema/` — dedicated schema-intelligence package: **planned, Phase 2+**.
- `nixus/llm/` — a single LLM client abstraction (model names/params are currently
  inline in the nodes): **planned, Phase 2+**.
- a `cli/` adapter: **planned, Phase 7**; a React `frontend/`: **planned, Phase 8**.

## The query entry point

`nixus/services/query_service.py::run_query(user_query, session_id)` runs a single
query through the compiled graph and returns the final state. **Adapters must go
through it** rather than re-implementing the graph-invocation sequence.

- The API's `POST /api/v1/run` handler is a thin shell: it builds a
  `RequestContext` (resolving the session id) and calls `run_query` with the
  plain `ctx.session_id` value — the core never receives the context type.
- **Gap:** the streaming path (`POST /api/v1/stream`, SSE via `astream_events`) still
  lives inline in `api/main.py` as of 1.1f. It moves into the service when a
  non-HTTP consumer needs streaming. Until then, only the non-streaming run is
  extracted. `get_thread_config` (LangGraph thread/checkpointer plumbing) lives in
  the service and is imported by the API's streaming/approve handlers.

## API versioning and request context (as of 1.3)

- **All endpoints are served under `/api/v1/`** (mounted via a single
  `APIRouter(prefix="/api/v1")` in `api/main.py`): `/api/v1/run`, `/api/v1/stream`,
  `/api/v1/run-sql`, `/api/v1/approve-write`, `/api/v1/cache-stats`,
  `/api/v1/cache-evict`, `/api/v1/fewshot-stats`, `/api/v1/health`. This is the
  stable contract for the UI, the future React frontend, and external consumers.
- **Health** is reachable at `/api/v1/health` and is *also* aliased, unversioned,
  at `/api/health` — the one intentional exception — for infrastructure probes
  (load balancers, uptime checks) that expect a version-independent path. (The
  docker-compose healthcheck probes Postgres with `pg_isready`, not this path.)
- **`RequestContext`** (`api/context.py`) is the API-layer carrier of per-request
  identity — **`session_id` only in V1**. Handlers build it per request and pass
  the plain `ctx.session_id` value across the core boundary (never the context
  type), so rule 1 holds. Auth identity will extend `RequestContext` later
  (Phase 8) without reshaping handler signatures.
- **No multi-tenancy in V1.** There is intentionally **no `tenant_id`** field,
  column, or convention anywhere. Tenancy is a V2 concern, addable later via a
  migration and a new `RequestContext` field — it is deliberately absent now.

## The nine rules every later prompt obeys

1. **One-way dependency direction.** Adapters import `nixus.*`. The core never
   imports `api`/`ui`/`cli`/`frontend`, and never imports `fastapi`/`starlette`/
   `streamlit`. (Enforced check: importing `nixus.services.query_service` must not
   pull `fastapi` into `sys.modules`.)
2. **SQL lives only in `nixus/db/`.** No raw SQL anywhere else.
3. **Route handlers contain no business logic.** A handler parses the request,
   calls a service, and shapes the HTTP response. ~15 lines is the smell threshold.
4. **Nodes are state-in / state-out.** A node takes the state and returns the
   state. No opening connections, no HTTP, no retry ownership inside a node; nodes
   use the `db/` stores and the LLM client.
5. **One config source: `nixus/config.py` (`settings`).** No scattered
   `os.getenv` / `os.environ` for configuration. (Adapter-process-local endpoints
   — the UI's `API_BASE_URL`, the eval harness's `NIXUS_API_URL`/`NIXUS_METRICS_FILE`
   — and the retired Chinook script's vars are the only documented exceptions.)
6. **Two DB connections never mix.** `state_db` (NIXUS's own tables: cache,
   embeddings, checkpoints) is separate from `target_db` (the user's data, queried
   read-only). **Current reality:** there is a *single* `DATABASE_URL` /
   connection today; the split lands in **Phase 2.1**. Until then, treat the
   distinction as intent and do not entangle NIXUS's own tables with user-data
   access in a way that blocks the split.
7. **All UI-relevant state is exposed as `/api/v1` JSON.** Nothing the UI needs
   may live only in Python memory. As of 1.3 every route is under `/api/v1/`
   (with `/api/health` kept as an unversioned infra alias).
8. **One responsibility per file.** Soft cap ~200 lines as a smell detector, not a
   hard limit.
9. **Tests mirror the source tree.** **Current reality:** tests live in `eval/` as
   benchmark/behavioral suites (`test_*.py`) rather than a `tests/` tree mirroring
   `nixus/`; as unit tests are added they should mirror the package they cover.
