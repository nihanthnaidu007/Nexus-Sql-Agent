# NIXUS SQL — Phase 0 Test Baseline

This is the reference baseline every later phase is checked against. It records
the harness-repair before/after and the benchmark numbers captured on a fully
seeded local stack. Distinct from `BENCHMARK.md` (the auto-rendered benchmark
report); this file is the human-authored baseline of record.

## Committed baseline — Phase 2.4 (2026-06-03): **51 passed / 2 failed / 53 total**

Phase 2 made introspection the **only** schema source: the handwritten Chinook
description seed (`scripts/seed_schema_embeddings.py`) and the `schema_source`
switch are gone; `schema_embeddings` is now populated purely by introspecting
the read-only target db (`python -m nixus.schema.reembed`), and the generation
prompts (`generate_sql.py`, `self_correct.py`) are table-agnostic — no Chinook
names. Chinook is now just one database NIXUS understands through the generic
path.

**New committed baseline: 51 passed / 2 failed / 53 total** (was 50/3/53).
**`D05` now PASSES**: introspection emits foreign-key join sentences in the
schema context (`Customer.SupportRepId references Employee.EmployeeId`), and a
generic, table-agnostic prompt rule ("when the question is about an entity
referenced by a foreign-key id, join to the referenced table and select its
name/label columns rather than the raw id") restores the guidance the old
Chinook-primed prompt had been carrying — so the generator now joins to
`Employee` and returns rep names instead of `SupportRepId` integers.

The **2 remaining failures** are product-accuracy edge cases, not regressions:
1. `test_sql_correctness[E02]` — column-shape overlap (correct values, extra
   columns reduce the text-fingerprint overlap). Schema-independent. **Owner: Phase 6.**
2. The cache-accuracy artifact (`test_cache_accuracy::test_paraphrase_hit_rate`
   on a cold cache, or `test_unrelated_miss_rate` on a warm one) — a semantic
   cache threshold sensitivity, not a SQL-correctness defect.

Regression floor for Phase 2+ is **51 passed**; `D05` passing is the guard.

### FLAG — few-shot cold-start (unresolved, out of scope for Phase 2)

Schema embeddings are now produced generically for any database via
introspection, but **few-shot examples are not**: a freshly-ingested user
database has introspected schema embeddings yet **zero** few-shot examples until
the system learns some at runtime. The Chinook few-shot pairs
(`scripts/seed_fewshot_examples.py`, intentionally **kept**) remain valid only
because Chinook is still the demo target. How to seed or bootstrap few-shot for
an arbitrary user database — or whether the generator should run example-free
until it self-learns — is **unresolved and deferred to a later phase**. Recorded
here so it is not lost.

---

> The Phase 0 baseline below is preserved as the historical record of when the
> harness was first stabilized; its 50/3/53 numbers predate the Phase 2 schema
> rework above.

## Run context

| Field | Value |
|---|---|
| Date | 2026-06-01 |
| Branch | `phase/0-stabilize` |
| Commit | `60d2a4cd944b3104ab9a12d5f4192fa7b2aa1f9f` |
| Python | 3.13.2 |
| OS | Darwin 25.5.0 (macOS, arm64) |
| Postgres | 16.13 — `pgvector/pgvector:pg16` |
| ANTHROPIC_API_KEY | present (value not recorded) |
| OPENAI_API_KEY | present (value not recorded) |
| `FULL_BENCHMARK_POSSIBLE` | **True** |
| **Baseline achieved** | **infra + full benchmark** |

## Harness repair (the core deliverable)

**Problem:** the eval suite is integration-only. The `http_client` fixture
intended to `pytest.skip` when `/api/health` is not 200, but a refused TCP
connection raised `httpx.ConnectError` *before* the status check. One test
(`test_cache_miss_latency`) opens a direct DB connection and raised
`OperationalError` on refusal. With infra down this produced errors, not skips.

**Fix (edited `eval/conftest.py` only):**
- Added `_probe_api()` / `_probe_db()` helpers that catch connection failures
  (`httpx.ConnectError`, `ConnectTimeout`, `ReadTimeout`, `OSError`; any DB
  exception) and return `False` instead of raising.
- Added a session-scoped `infra_status` fixture that probes API + Postgres
  **once** per session.
- Added an `autouse` `_require_infra` fixture that `pytest.skip`s **every**
  integration test (including the direct-DB latency test) with one actionable
  message when either service is unreachable.
- Hardened `http_client` to depend on `infra_status` and skip instead of
  constructing a client against a dead server.
- **No assertions were weakened and no product was mocked.** `test_latency.py`
  was not modified — the single session probe covers its direct-DB test, so a
  per-test guard would have been duplication.

Skip messages are actionable (the "errors that teach" principle), e.g.:
> API not reachable at http://localhost:8000. Infrastructure is not running.
> Start it, then re-run the eval suite:
>   1. `docker compose up -d db`   # Postgres on localhost:5433
>   2. `uvicorn api.main:app --host 0.0.0.0 --port 8000`

**Before vs after (infra DOWN, `pytest eval/ -q`):**

| State | passed | skipped | failed | errors |
|---|---|---|---|---|
| Before repair | 0 | 0 | 1 | **52** |
| After repair | 0 | **53** | 0 | **0** |

Zero connection-driven errors remain; the suite skips cleanly.

## Infra baseline (always recorded)

Infra brought up against the **existing local `nexus_sql` volume** (see naming
note below). `/api/health`:

```json
{ "status": "ok", "db_connected": true, "anthropic_connected": true,
  "openai_connected": true, "langsmith_tracing": true, "version": "1.0.0" }
```
12 graph nodes registered: parse_intent, safety_check, check_cache,
retrieve_schema, retrieve_fewshot, generate_sql, validate_syntax, execute_query,
check_result, self_correct, classify_chart, explain_result.

**Tables present** in `nexus_sql` (18 total):
- Chinook (11): Album, Artist, Customer, Employee, Genre, Invoice, InvoiceLine,
  MediaType, Playlist, PlaylistTrack, Track — 275 artists confirmed.
- App: `schema_embeddings` (11 rows), `fewshot_examples` (86 rows),
  `query_cache` (53 rows).
- Checkpointer (4): checkpoints, checkpoint_blobs, checkpoint_writes,
  checkpoint_migrations.

**pytest with infra UP:** 53 collected → **50 passed, 3 failed, 0 errors,
0 skipped**.

## Full query benchmark (FULL_BENCHMARK_POSSIBLE = True)

Command: `python eval/run_benchmark.py` → writes `eval/benchmark_results.json`,
renders `BENCHMARK.md`. Duration **270.5s**. Result: **50 passed / 3 failed /
53 total**; runner reported "✅ All non-negotiable bars met."

**Metrics** (`eval/benchmark_metrics.json`):

| Metric | Value |
|---|---|
| Paraphrase cache hit rate | 0.80 (4/5) |
| Unrelated miss rate | 0.00 (0/5) — *see failure below* |
| Cache-miss latency | p50 6468 ms · p95 8690 ms · p99 9053 ms (n=5) |
| Cache-hit latency | p50 1439 ms · p95 1922 ms · p99 1940 ms (n=10) |

**3 failing tests (pre-existing accuracy edge cases — same set as the prior
committed run; non-blocking per the runner's bars):**
1. `test_cache_accuracy.py::test_unrelated_miss_rate` — unrelated miss rate
   0.0% < 80% target (semantic cache matched supposedly-unrelated pairs).
2. `test_sql_correctness.py::test_sql_correctness[D05]` — overlap 0%: returned
   `SupportRepId` integers instead of sales-rep names.
3. `test_sql_correctness.py::test_sql_correctness[E02]` — overlap 39%: correct
   rows but extra columns (Country, Email) reduced the text-fingerprint overlap.

These are **product accuracy** items for later phases, not harness or infra
defects. They define the accuracy floor: regressions below 50 passed are a
failure; fixing any of these three is an improvement.

## Findings (for later phases)

- **DB-name / volume mismatch (from Phase 0.2):** the local `.env` still points
  `DATABASE_URL` at `nexus_sql`, and the existing Docker volume
  `nexus-sql-agent_pgdata` was initialized **before** the rename, so Postgres
  ignores the renamed compose values (`POSTGRES_USER/DB=nixus`) and keeps role
  `nexus` / db `nexus_sql`. The baseline therefore ran against `nexus_sql`. To
  move to `nixus_sql`, recreate the volume per the `.env.example` note
  (`docker compose down -v && up -d`) — **the user's call; not done here** —
  and update the local `.env`.
- **Boot dependency:** `db/connection.py` raises `RuntimeError` at import if
  `DATABASE_URL` is unset, and `eval/conftest.py` imports it — so `DATABASE_URL`
  must be present (via `.env`) even to *collect* tests. The API also performs a
  live LLM connectivity check at startup but starts fine without keys for the
  non-LLM paths (health reports `*_connected: false`).

## How to reproduce this baseline

```bash
# 1. Postgres (uses existing nexus_sql volume)
docker compose up -d db

# 2. API on the port the tests default to (:8000)
uvicorn api.main:app --host 0.0.0.0 --port 8000      # needs .env with DATABASE_URL + keys

# 3. Full benchmark (requires Anthropic + OpenAI keys)
python eval/run_benchmark.py                          # -> benchmark_results.json + BENCHMARK.md

# Harness-skip behavior (with infra DOWN) — should report "53 skipped", 0 errors
python -m pytest eval/ -q
```
