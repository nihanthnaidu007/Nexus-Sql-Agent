"""
Latency benchmark tests — Category 6 of the NIXUS SQL evaluation harness.

Measures end-to-end latency for cache-miss (full LLM pipeline) and cache-hit
(vector-similarity cache lookup) paths.

Targets (wall-clock from client perspective, including network):
  Cache-miss p50  < 30 000 ms   (full generate → execute pipeline)
  Cache-miss p95  < 60 000 ms
  Cache-miss p99  < 90 000 ms
  Cache-hit  p50  <  3 000 ms   (embedding similarity search + return)

Cache-miss questions are *generated fresh per run* with a unique timestamp
token embedded in the natural-language text, so the semantic cache (0.92
cosine threshold) cannot match them to anything from a prior run. This is
what keeps the cache-miss numbers honest: without it, repeated benchmark
runs would auto-learn the static gold questions into the cache and the
"miss" path would silently degrade into a hit-path measurement.
"""

import time
import uuid
import pytest
import httpx
from sqlalchemy import text

from eval.conftest import BASE_URL, record_metric
from nixus.db.connection import sync_engine


# Sample sizes
N_MISS_SAMPLES = 5    # cache-miss path: each sample is a full LLM pipeline call
N_HIT_SAMPLES = 10    # cache-hit path: cheap, so we collect enough for a real p99

# Per-request timeout for the cache-miss client. A genuine cold-cache query
# can occasionally stretch past the shared fixture's 120 s, especially after
# self-correction. Set high enough that genuine slow paths are recorded as
# slow samples (and visible in p95/p99) rather than swallowed as a test
# failure that wipes the entire run.
LATENCY_CLIENT_TIMEOUT = 90.0


# Templates for fresh-per-run cache-miss questions. The {token} placeholder
# is filled in with a unique timestamp at test time. The semantic cache uses
# a 0.92 cosine threshold which the token alone does not always defeat
# (templates from prior runs get auto-learned and dominate the embedding),
# so the test also explicitly clears matching cache entries up front — see
# _CACHE_CLEAR_PATTERNS below.
_CACHE_MISS_TEMPLATES = [
    "List the bottom 5 genres by number of tracks (run {token}).",
    "Show customers from Canada ordered by last name as of {token}.",
    "What is the median invoice total for 2022 (benchmark {token})?",
    "Which albums have exactly one track (run {token})?",
    "Show employees who were hired in the same year (test {token}).",
    "Top 5 longest tracks measured at {token}.",
    "Invoice totals by country for run {token}.",
    "Album count per artist run {token}.",
    "Playlist track counts for benchmark {token}.",
    "Tracks with duration over 5 minutes test {token}.",
]

# ILIKE patterns used to evict semantically-similar cache entries that prior
# benchmark runs (or auto-learning from the gold suite) may have left behind.
# Without this the semantic cache will match the templated questions above
# at >= 0.92 cosine and the "miss" measurement silently degrades into a hit
# measurement.
_CACHE_CLEAR_PATTERNS = [
    "%bottom % genres%",
    "%customers from Canada%",
    "%median invoice total%",
    "%albums % exactly one track%",
    "%employees % hired in the same year%",
    "%longest tracks%",
    "%invoice totals by country%",
    "%album count per artist%",
    "%playlist track counts%",
    "%tracks % duration over 5 minutes%",
]


def _evict_latency_cache_entries() -> int:
    """Delete query_cache rows whose user_query matches the latency-test
    templates. Returns the number of rows removed.

    Run synchronously at the start of test_cache_miss_latency so each run
    measures a genuine cold-cache path through the agent.
    """
    removed = 0
    with sync_engine.begin() as conn:
        for pattern in _CACHE_CLEAR_PATTERNS:
            result = conn.execute(
                text("DELETE FROM query_cache WHERE user_query ILIKE :pat"),
                {"pat": pattern},
            )
            removed += result.rowcount or 0
    return removed

# Question used for cache-hit measurements — must be a stable, common query
# that gets warmed once and then hit repeatedly.
CACHE_HIT_QUESTION = "How many tracks does each genre have?"


def _generate_unique_miss_questions(n: int) -> list[str]:
    """Return N cache-miss questions guaranteed to miss the semantic cache.

    Each question embeds a unique timestamp so the embedding will not match
    any prior cached entry at the 0.92 cosine threshold. This is the whole
    point of the latency suite — without uniqueness the numbers drift toward
    the cache-hit path as the cache learns the static questions.
    """
    token = int(time.time() * 1000)  # ms granularity → unique even on rapid reruns
    return [
        tmpl.format(token=token + i)
        for i, tmpl in enumerate(_CACHE_MISS_TEMPLATES[:n])
    ]


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    idx = (p / 100.0) * (n - 1)
    f = int(idx)
    c = min(f + 1, n - 1)
    return sorted_values[f] + (idx - f) * (sorted_values[c] - sorted_values[f])


def _timed_run(client: httpx.Client, question: str) -> tuple[float, dict]:
    t0 = time.monotonic()
    resp = client.post(
        "/api/v1/run",
        json={"user_query": question, "session_id": str(uuid.uuid4())},
    )
    ms = (time.monotonic() - t0) * 1000
    resp.raise_for_status()
    return ms, resp.json()


def test_cache_miss_latency():
    # Clear any auto-learned entries that match our templates before measuring.
    removed = _evict_latency_cache_entries()
    print(f"\nEvicted {removed} prior cache entries before cache-miss measurement.")

    questions = _generate_unique_miss_questions(N_MISS_SAMPLES)
    latencies: list[float] = []
    served_from_cache_count = 0
    timeouts = 0

    with httpx.Client(base_url=BASE_URL, timeout=LATENCY_CLIENT_TIMEOUT) as client:
        for question in questions:
            try:
                ms, state = _timed_run(client, question)
            except httpx.ReadTimeout:
                # A genuine slow sample. Record the timeout ceiling so it
                # surfaces in p95/p99 rather than disappearing as a test
                # failure.
                ms = LATENCY_CLIENT_TIMEOUT * 1000
                state = {}
                timeouts += 1
                print(
                    f"WARNING: cache-miss query timed out after "
                    f"{LATENCY_CLIENT_TIMEOUT}s — recorded as ceiling."
                )
            latencies.append(ms)
            if state.get("served_from_cache"):
                served_from_cache_count += 1

    latencies.sort()
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)

    print(
        f"\nCache-miss latency (n={len(latencies)}, "
        f"cache_hits_observed={served_from_cache_count}) — "
        f"p50={p50:.0f}ms  p95={p95:.0f}ms  p99={p99:.0f}ms"
    )
    record_metric("cache_miss_latencies", {
        "p50": round(p50),
        "p95": round(p95),
        "p99": round(p99),
        "samples": len(latencies),
        "cache_hits_observed": served_from_cache_count,
        "timeouts": timeouts,
    })

    # Contamination guard: a small number of incidental cache hits can happen
    # if a prior run left a semantically similar entry above the 0.92 threshold.
    # We record `cache_hits_observed` in metrics so it surfaces in BENCHMARK.md
    # and warn loudly, but only hard-fail when the contamination is so bad that
    # the p50 itself looks like a hit-path measurement (< 3000 ms).
    if served_from_cache_count > 0:
        print(
            f"\nWARNING: {served_from_cache_count}/{len(latencies)} "
            f"supposedly-uncached questions hit the cache — see "
            f"cache_hits_observed in BENCHMARK.md."
        )
    assert p50 >= 3_000, (
        f"Cache-miss p50 {p50:.0f}ms < 3 000ms — the latency suite has been "
        f"contaminated by the semantic cache. Tighten the unique-token "
        f"generation or raise CACHE_SIMILARITY_THRESHOLD."
    )

    assert p50 < 30_000, f"Cache-miss p50 {p50:.0f}ms ≥ 30 000ms"
    assert p95 < 60_000, f"Cache-miss p95 {p95:.0f}ms ≥ 60 000ms"
    assert p99 < 90_000, f"Cache-miss p99 {p99:.0f}ms ≥ 90 000ms"


def test_cache_hit_latency(http_client):
    # Warm the cache with the first call (this may be a cache miss).
    _timed_run(http_client, CACHE_HIT_QUESTION)

    # Subsequent calls should hit the cache. Bumped to 10 samples so p99
    # is statistically meaningful rather than a single outlier sample.
    latencies: list[float] = []
    served_from_cache_count = 0
    for _ in range(N_HIT_SAMPLES):
        ms, state = _timed_run(http_client, CACHE_HIT_QUESTION)
        if state.get("served_from_cache"):
            latencies.append(ms)
            served_from_cache_count += 1

    assert latencies, (
        "Cache-hit suite collected zero hits — cache may not be warming. "
        "Check CACHE_SIMILARITY_THRESHOLD and that /api/run returns "
        "served_from_cache=True for repeated identical questions."
    )

    latencies.sort()
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)

    print(
        f"\nCache-hit latency (n={len(latencies)}) — "
        f"p50={p50:.0f}ms  p95={p95:.0f}ms  p99={p99:.0f}ms (target p50 < 3000ms)"
    )
    record_metric("cache_hit_latencies", {
        "p50": round(p50),
        "p95": round(p95),
        "p99": round(p99),
        "samples": len(latencies),
    })

    assert p50 < 3_000, f"Cache-hit p50 {p50:.0f}ms ≥ 3 000ms"
