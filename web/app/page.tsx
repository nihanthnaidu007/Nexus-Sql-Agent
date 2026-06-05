"use client";

/**
 * NIXUS SQL — Phase 8.3: the trust model made visible.
 *
 * This page owns the conversation. Three trust behaviors are now first-class:
 *   · ANSWERED            → AnswerView, with the ConfidenceBanner (level + reasons)
 *   · NEEDS_CLARIFICATION → Clarification, a real threaded round-trip (N=2, server-
 *                           enforced); the answer continues the SAME conversation
 *   · REFUSED_*           → Refusal, designed as a deliberate, legitimate outcome
 *
 * A refusal is NOT an error. The error panel below is reserved for an actual
 * request failure (network / 500), which is visually and semantically distinct.
 *
 * The API contract is unchanged: runQuery() still POSTs /api/v1/run; the
 * clarification follow-up only populates request fields RunRequest already declares.
 */

import { useState } from "react";
import {
  runQuery,
  ApiError,
  type NormalizedResult,
  type ClarificationExchange,
} from "@/lib/api";
import { QueryForm } from "@/components/QueryForm";
import { AnswerView, RunningState } from "@/components/ResultView";
import { Clarification, ConversationContext } from "@/components/Clarification";
import { Refusal } from "@/components/Refusal";

/** An in-progress / completed clarification thread for the current conversation. */
interface Thread {
  originalQuestion: string;
  sessionId: string;
  exchanges: ClarificationExchange[];
}

export default function Page() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<NormalizedResult | null>(null);
  const [thread, setThread] = useState<Thread | null>(null);
  const [error, setError] = useState<{ message: string; traceId?: string } | null>(
    null,
  );

  /** A fresh, top-level question — resets any prior clarification thread. */
  async function submitFresh() {
    const q = question.trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setThread(null);
    try {
      const r = await runQuery(q);
      setResult(r);
      // If the system needs clarification, open a thread anchored to this question.
      if (r.isClarification) {
        setThread({ originalQuestion: q, sessionId: r.sessionId, exchanges: [] });
      }
    } catch (err) {
      setError(toError(err));
    } finally {
      setLoading(false);
    }
  }

  /** Answer the current clarifying question — threaded into the SAME conversation. */
  async function answerClarification(answer: string) {
    if (!thread || !result || loading) return;
    setLoading(true);
    setError(null);
    // Record this turn (the question the server just asked + the user's answer).
    const exchanges: ClarificationExchange[] = [
      ...thread.exchanges,
      { question: result.clarifyingQuestion, answer },
    ];
    try {
      // user_query echoes the latest answer; the server folds the full context and
      // decides termination (N=2) itself via clarification_round.
      const r = await runQuery(answer, {
        sessionId: thread.sessionId,
        clarificationContext: {
          original_question: thread.originalQuestion,
          prior_clarifications: exchanges,
        },
        clarificationRound: exchanges.length,
      });
      setThread({ ...thread, exchanges });
      setResult(r);
    } catch (err) {
      setError(toError(err));
    } finally {
      setLoading(false);
    }
  }

  const showThreadContext =
    thread && result && !result.isClarification && thread.exchanges.length > 0;

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
        onSubmit={submitFresh}
        loading={loading}
      />

      {loading && <RunningState />}

      {/* ACTUAL error (request failed) — distinct from a refusal. */}
      {error && !loading && (
        <div className="notice error" role="alert">
          <div className="notice-label">Request failed</div>
          <div className="notice-body">{error.message}</div>
          {error.traceId && <div className="trace">trace · {error.traceId}</div>}
        </div>
      )}

      {result && !loading && !error && (
        <>
          {/* Light context above a terminal outcome that came from clarification. */}
          {showThreadContext && thread && (
            <div className="thread-context">
              <ConversationContext
                originalQuestion={thread.originalQuestion}
                exchanges={thread.exchanges}
              />
            </div>
          )}

          {result.isClarification && thread && (
            <Clarification
              originalQuestion={thread.originalQuestion}
              exchanges={thread.exchanges}
              question={result.clarifyingQuestion}
              onAnswer={answerClarification}
              loading={loading}
            />
          )}

          {result.isRefusal && (
            <Refusal outcome={result.outcome} reason={result.refusalReason} />
          )}

          {result.isAnswer && <AnswerView result={result} />}
        </>
      )}
    </main>
  );
}

function toError(err: unknown): { message: string; traceId?: string } {
  if (err instanceof ApiError) return { message: err.message, traceId: err.traceId };
  return { message: err instanceof Error ? err.message : String(err) };
}
