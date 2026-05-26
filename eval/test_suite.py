"""
NEXUS SQL Evaluation Suite
--------------------------
Implemented in Phase 8. See individual test files:

  eval/test_sql_correctness.py   30 parametrized queries vs gold SQL
  eval/test_cache_accuracy.py    paraphrase hit rate, unrelated miss rate
  eval/test_self_correction.py   5 tricky queries testing resilience
  eval/test_safety.py            WRITE detection, READ pass-through, injection blocking
  eval/test_chart_classification.py  7 chart type tests via /api/run-sql
  eval/test_latency.py           cache-miss p50/p95/p99, cache-hit p50

Run the suite:
    python eval/run_benchmark.py

Run fast (no LLM) tests only:
    pytest eval/test_chart_classification.py eval/test_safety.py::test_sql_injection_blocked
"""
