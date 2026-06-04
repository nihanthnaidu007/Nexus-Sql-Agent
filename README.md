# ◈ NIXUS SQL

A read-only, database-agnostic **Text-to-SQL agent** built on LangGraph. Its
design priority is **trust over capability**: it refuses out-of-scope, write, and
ambiguous requests, and surfaces uncertainty rather than fabricating an answer.
It is read-only *by construction* — every query runs through a PostgreSQL role
that holds only `SELECT` — and it works on any PostgreSQL schema by introspecting
it, with no per-database configuration. The honest measure of this project is in
the [benchmark](#honest-benchmark--known-limitations) section below: real numbers,
including the two questions it gets wrong and why.

![NIXUS SQL — query input and state machine](images/image%201.png)
![NIXUS SQL — table view with AI insight](images/image%202.png)

---

## Quick start — the self-contained demo

The default `docker compose up` stands up everything: both databases, the
read-only role, the bundled SaaS sample data (loaded + seeded), the schema
migrations, the schema embeddings, and the API. **The only thing you must
provide is two API keys.** No connection string, no external database.

```bash
git clone <repo-url> && cd Nexus-Sql-Agent
cp .env.example .env          # then set ANTHROPIC_API_KEY and OPENAI_API_KEY in .env
docker compose up -d --build  # provisions both DBs, seeds SaaS, migrates, embeds, boots the API

# once healthy:
nixus query "how many organizations are there?"
```

On first boot the API container runs, in strict idempotent order: wait for
Postgres → apply migrations → ensure the SaaS sample is loaded + seeded → check
the API keys (**fail fast** with a clear message if missing) → embed the target
schema → start the API. If a key is missing it stops with a readable error
instead of booting broken.

Notes on setup safety:
- **Your `.env` is never clobbered.** `scripts/setup.sh` (and the manual `cp`)
  only create `.env` when one does not already exist — an existing file with real
  keys is left untouched.
- **Comments in `.env.example` are on their own lines**, so a value is never
  polluted by a trailing comment. Set the value after the `=` and put nothing
  else on that line.

`scripts/setup.sh` is an optional guided path: it creates `.env` (if absent),
prompts for the two keys without echoing them, and brings the stack up.

---

## What you can ask — and what it refuses

Against the bundled SaaS sample (tables: `organizations`, `users`,
`subscriptions`, `plans`, `invoices`, `payments`, `usage_events`):

```bash
nixus query "how many organizations are there?"
nixus query "which organization has the most users?"
nixus query "what is the total revenue from paid invoices?"
nixus query "how many users per role?"
```

What it **refuses**, and how the refusal surfaces — this is the trust model in
action:

| You ask | NIXUS does |
| --- | --- |
| `delete all users` / `drop the invoices table` | **Refuses** — it is read-only; write operations are never generated or run |
| `show me the top ones` / `give me the stuff` | **Asks for clarification** — the request is too ambiguous to answer faithfully |
| `how are things going` | **Declines as out of scope** — not a question about the data |

A refusal is a valid, deliberate outcome — not an error.

---

## Health — and what the fields mean

The HTTP endpoint `GET /api/health` reports dependency status honestly and always
returns **HTTP 200** when the API process is alive (a failed dependency changes a
body field, never the status):

```jsonc
{
  "status": "ok",                 // "ok" only when db + both LLM providers check out
  "db_connected": true,
  "anthropic_connected": true,    // a REAL credential check, not just "is a key set"
  "openai_connected": true,       // a placeholder/empty key reports false, no API call made
  "langsmith_tracing": false,     // tracing is opt-in; off unless a valid LangSmith key is set
  "llm_last_checked": 1234567.89  // the provider probe is cached, so polling is cheap
}
```

`anthropic_connected` / `openai_connected` reflect an actual probe of the
credential: a placeholder or empty key reports `false` **without making an API
call**, and a real key is verified with a cached probe. Tracing is off by default
and turns on only when a valid `LANGCHAIN_API_KEY` is present — a placeholder key
produces no tracing and no error noise.

The CLI has its own lightweight check for database reachability:

```bash
nixus health        # pings state_db and target_db (SELECT 1 on each)
```

---

## Using your own database (step two)

Bring your own PostgreSQL. NIXUS needs **only `SELECT`** on the target — ideally a
read replica or a `SELECT`-only role. It never writes to your data; read-only is
enforced by Postgres, not by the app.

```bash
# Point the whole stack (API + embeddings + benchmark) at one target, then re-embed:
scripts/use_target.sh postgresql://readonly_user:pw@your-host:5432/yourdb
# restart the API so it serves the new target:
#   docker: docker compose restart api
#   local : re-run the API process
nixus query "..."   # now answers against your schema
```

The same single command switches between the bundled samples:

```bash
scripts/use_target.sh saas        # the bundled SaaS sample (default)
scripts/use_target.sh chinook     # the alternate Chinook sample
```

---

## CLI

```bash
nixus query "how many organizations are there?"   # ask a question against the configured DB
nixus health                                       # check state_db + target_db reachability
nixus reembed                                      # re-introspect + re-embed the target schema
```

---

## Honest benchmark + known limitations

The benchmark of record runs a fixed, held-out **SaaS gold set** against the
deterministic `nixus_saas` seed, scored by result-equivalence (not string match).
The measured result:

- **Answerable: 55 / 57 correct** — easy **13/13**, medium **15/17**, hard **27/27**.
- **Scope: 10 / 10** — it correctly refuses or clarifies every case it should.

These numbers are not rounded and not softened. There are **two** genuine
failures, and they are documented here rather than hidden:

- **M3 — a faithfulness gap (the most important known limitation).** On some
  questions the system produces a well-formed query that *quietly narrows the
  request* — adding a filter the user did not ask for (e.g. `WHERE is_active =
  true`). This passes grounding because **grounding verifies that every table and
  column the SQL references actually exists — it does not verify that the SQL is a
  *faithful* representation of the question.** A query can be fully grounded and
  still answer a slightly different question than the one asked. This is an
  architectural boundary of the current pipeline, not a bug we have patched over.

- **M11 — a `DISTINCT` omission.** On some "which organizations…" questions the
  system omits `DISTINCT` and returns duplicate rows where the faithful answer is
  a distinct set.

Neither is fixed. They are stated so the numbers can be trusted.

The benchmark is reproducible:

```bash
scripts/use_target.sh saas
.venv/bin/python eval/run_saas_benchmark.py
```

The harness lives in [`eval/`](eval/); the gold set is
[`eval/saas_gold.py`](eval/saas_gold.py) and the report of record is
[`eval/saas_benchmark_results.json`](eval/saas_benchmark_results.json).

---

## Architecture

NIXUS is one **framework-agnostic core** (`nixus/`) wrapped by **thin adapters**
(the FastAPI service in `api/`, the CLI in `nixus/cli.py`). All query logic —
scope classification, schema and few-shot retrieval, SQL generation, syntax
validation, grounding, execution, result checking, and explanation — lives in a
LangGraph node pipeline behind a single entry point,
`nixus/services/query_service.py::run_query`, which imports no web framework. The
system uses **two databases**: a read-write **state** database (NIXUS-owned
bookkeeping: schema embeddings, few-shot examples, query cache, migrations, and
the LangGraph checkpointer) and a strictly read-only **target** database (your
data). Semantic retrieval and caching use **pgvector**.

For the full module map and the rules each layer obeys, see
[ARCHITECTURE.md](ARCHITECTURE.md).

---

## License

Licensed under the **Apache License 2.0** — see [LICENSE](LICENSE).

Copyright 2026 Nihanth Naidu Kalisetti.
