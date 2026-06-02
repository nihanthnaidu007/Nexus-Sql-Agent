"""
NIXUS SQL Evaluation Metrics
-----------------------------
Implemented in Phase 8. Metrics are computed by eval/report.py from
pytest-json-report output. Run `python eval/run_benchmark.py` to generate
BENCHMARK.md with all metric values.

Implemented metrics:
  - sql_correctness_rate: % of queries where result set matches gold SQL
    (text fingerprint comparison, ≥70% row overlap threshold per query)
  - cache_hit_precision: paraphrase hit rate vs unrelated miss rate
  - self_correction_rescue_rate: % of tricky queries resolved without final error
  - safety_classification_accuracy: WRITE detection and READ pass-through rates
  - injection_block_rate: % of SQL injection attempts rejected (must be 100%)
  - chart_classification_accuracy: % correct chart type (line/bar/pie/scatter/none)
  - p50_latency_ms, p95_latency_ms, p99_latency_ms: end-to-end wall-clock latency

See eval/conftest.py for the comparison helpers and eval/report.py for the
BENCHMARK.md generator.
"""
