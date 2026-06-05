# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-06-04

First public release. NIXUS SQL is a read-only, database-agnostic Text-to-SQL
agent built on LangGraph, whose design priority is **trust over capability**.

### Added

**Trust pipeline**
- Scope classification that refuses out-of-scope, write, and ambiguous requests
  rather than answering them — refusal and clarification are first-class outcomes.
- A grounding check that verifies every table and column the generated SQL
  references actually exists in the schema before the query runs.
- Descriptive-only result explanations (the agent describes what the data shows,
  it does not editorialize or infer beyond the result).
- Honest, categorical confidence reporting on each answer.

**Database-agnostic, read-only by construction**
- Works on any PostgreSQL schema via introspection — no per-database configuration.
- The target database is accessed through a Postgres role that holds only
  `SELECT`; read-only is enforced by Postgres, not by the application.
- A two-database split: a read-write **state** database (NIXUS-owned bookkeeping —
  schema embeddings, few-shot examples, query cache, migrations, and the LangGraph
  checkpointer) and a strictly read-only **target** database.

**Self-contained demo and operations**
- One-command bring-up (`docker compose up`) that provisions both databases, the
  read-only role, the bundled SaaS sample data, the migrations, the schema
  embeddings, the API, and the React web UI — the only required input is two API
  keys.
- A single target switch (`scripts/use_target.sh <saas|chinook|url>`) that points
  the API, embeddings, and benchmark at one target and re-embeds in step.
- A CLI: `nixus query`, `nixus health`, `nixus reembed`.
- An honest `/api/health` endpoint: `*_connected` reflects a real cached
  credential probe (a placeholder/empty key reports `false` with no API call), and
  the endpoint always returns HTTP 200 when the process is alive.
- Opt-in LangSmith tracing: off by default; a placeholder key produces no tracing
  and no error noise.
- The Docker image builds from `requirements.lock` for a fully pinned environment.

**React web UI**
- A hand-built React (Next.js) frontend, served at `http://localhost:3000`, that
  makes the trust model visible: the generated SQL, result table, and insight for
  an answer; the categorical **confidence** with its reasons; the **clarification**
  round-trip (honoring server-enforced N=2 termination); and the **refusal** states
  designed as deliberate, legitimate outcomes, kept distinct from an actual request
  error. It consumes the same `POST /api/v1/run` endpoint as the CLI and adds no
  system capability — it makes the proven pipeline legible. This frontend replaces
  the earlier Streamlit prototype, which has been retired.

**Honest benchmark**
- A fixed, held-out SaaS gold set scored by result-equivalence. Result of record:
  **55/57 answerable** (easy 13/13, medium 15/17, hard 27/27) and **10/10 scope**.
  Reproducible via `eval/run_saas_benchmark.py`.

### Known limitations

- **M3 — faithfulness gap.** On some questions the system produces a well-formed,
  fully grounded query that quietly narrows the request (e.g. an unrequested
  `WHERE is_active = true`). Grounding verifies that referenced tables/columns
  exist; it does not verify that the SQL faithfully represents the question. This
  is an architectural boundary, not a fixed defect.
- **M11 — `DISTINCT` omission.** On some "which organizations…" questions the
  system omits `DISTINCT` and returns duplicate rows.

### Not in this release

Explicitly out of scope for V1, to set expectations honestly:
- No write mode (writes are refused, never executed).
- No authentication or authorization.
- No usage telemetry.
- No multi-tenancy.

[1.0.0]: https://keepachangelog.com/en/1.0.0/
