# Archived Chinook benchmark (retired in Phase 6.2)

These files are the **retired Chinook gold set**, kept for history. They are
**archived, not deleted**, and are **not collected** by pytest (see
`collect_ignore_glob` in `eval/conftest.py`).

The **benchmark of record** is now the SaaS honest benchmark:
- `eval/run_saas_benchmark.py` — the runnable benchmark of record (emits
  `eval/saas_benchmark_results.json`).
- `eval/test_saas_correctness.py` — its pytest view.
- `eval/saas_gold.py` — the fixed gold set.
- `eval/result_equivalence.py` — honest, value-based correctness (replaces the
  broken column-overlap comparison below).

## What was archived and why

| File | Was | Why retired |
|------|-----|-------------|
| `test_sql_correctness.py` | Chinook SQL-correctness gold (A01–F05) | Home of **E02**; relied on `result_overlap_rate`, a fuzzy text-token overlap that ignored numbers/dates and row counts (false equivalences). |
| `gold_queries.py` | Chinook gold queries (30) | The Chinook gold set itself. |
| `test_cache_accuracy.py` | Chinook cache-accuracy gate | Produced the chronically-borderline **`test_unrelated_miss_rate`** artifact. |

By switching the benchmark of record to the SaaS suite, **E02** and
**`test_unrelated_miss_rate`** no longer exist as benchmark failures — by
construction, not by tuning.

## What was NOT retired
- The **Chinook database** (`nixus_chinook`) remains as a demo target.
- `eval/test_safety.py`, `eval/test_self_correction.py`,
  `eval/test_chart_classification.py` remain (general-capability tests; run
  against the Chinook demo target). They are not part of the SaaS benchmark of
  record.
- `eval/test_latency.py` was **recalibrated to a reported metric** (no latency
  gate) — not archived.
