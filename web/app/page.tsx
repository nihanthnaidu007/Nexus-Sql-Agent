"use client";

/**
 * NIXUS SQL — Phase 8.2 happy-path query UI.
 *
 * The designed normal-answer experience: ask a question → see the SQL it ran →
 * the result table → the insight. Refusal / clarification / error paths from 8.1
 * still render (minimally) without crashing; their full design is 8.3.
 *
 * The API contract is UNCHANGED from 8.1: this page calls the same runQuery()
 * (POST /api/v1/run, { user_query }) and consumes the same NormalizedResult.
 * 8.2 changes presentation only.
 */

import { useState } from "react";
import { runQuery, ApiError, type NormalizedResult } from "@/lib/api";
import { QueryForm } from "@/components/QueryForm";
import { ResultView, RunningState } from "@/components/ResultView";

export default function Page() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<NormalizedResult | null>(null);
  const [error, setError] = useState<{ message: string; traceId?: string } | null>(
    null,
  );

  async function submit() {
    const q = question.trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await runQuery(q));
    } catch (err) {
      // Honest error surfacing — never a blank screen, never a swallowed throw.
      if (err instanceof ApiError) {
        setError({ message: err.message, traceId: err.traceId });
      } else {
        setError({ message: err instanceof Error ? err.message : String(err) });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <header className="masthead">
        <h1 className="wordmark">
          NIXUS<span className="dot">.</span>
        </h1>
        <span className="tagline">natural language → SQL · read-only</span>
      </header>

      <QueryForm
        value={question}
        onChange={setQuestion}
        onSubmit={submit}
        loading={loading}
      />

      {loading && <RunningState />}

      {error && !loading && (
        <div className="notice error" role="alert">
          <div className="notice-label">Request failed</div>
          <div className="notice-body">{error.message}</div>
          {error.traceId && <div className="trace">trace · {error.traceId}</div>}
        </div>
      )}

      {result && !loading && <ResultView result={result} />}
    </main>
  );
}
