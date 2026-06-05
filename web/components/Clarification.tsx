"use client";

/**
 * The clarification round-trip — the system asking rather than guessing.
 *
 * This is the product's most distinctive interaction. NEEDS_CLARIFICATION is NOT
 * an error: it's NIXUS saying "I need one more thing to answer this well." The
 * answer is threaded back into the SAME conversation (see page.tsx + api.ts) using
 * the real stateless contract; the server enforces the N=2 cap, so the UI just
 * renders whatever terminal outcome comes back (answer or REFUSED_AMBIGUOUS).
 */
import { useState } from "react";
import type { ClarificationExchange } from "@/lib/api";

/** Lightweight thread context: the original question + any answered turns. Shown
 *  during clarification AND above a terminal outcome so the user knows what is
 *  being answered. */
export function ConversationContext({
  originalQuestion,
  exchanges,
}: {
  originalQuestion: string;
  exchanges: ClarificationExchange[];
}) {
  return (
    <div className="convo">
      <div className="convo-turn">
        <span className="convo-who">You asked</span>
        <span className="convo-text">{originalQuestion}</span>
      </div>
      {exchanges.map((ex, i) => (
        <div key={i}>
          <div className="convo-turn convo-ask">
            <span className="convo-who">NIXUS asked</span>
            <span className="convo-text">{ex.question}</span>
          </div>
          <div className="convo-turn">
            <span className="convo-who">You answered</span>
            <span className="convo-text">{ex.answer}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function Clarification({
  originalQuestion,
  exchanges,
  question,
  onAnswer,
  loading,
}: {
  originalQuestion: string;
  exchanges: ClarificationExchange[];
  question: string;
  onAnswer: (answer: string) => void;
  loading: boolean;
}) {
  const [answer, setAnswer] = useState("");

  function submit() {
    const a = answer.trim();
    if (!a || loading) return;
    onAnswer(a);
    setAnswer("");
  }

  return (
    <section className="clarify" aria-label="NIXUS needs clarification">
      <ConversationContext
        originalQuestion={originalQuestion}
        exchanges={exchanges}
      />

      <div className="clarify-ask">
        <span className="clarify-kicker">NIXUS needs one detail</span>
        <p className="clarify-question">{question}</p>

        <form
          className="query-field clarify-field"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <span className="query-prompt" aria-hidden>
            ↳
          </span>
          <textarea
            className="query-input"
            aria-label="Your answer to the clarifying question"
            rows={1}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Answer to refine the question…"
            disabled={loading}
            autoFocus
          />
          <button
            className="query-submit"
            type="submit"
            disabled={loading || !answer.trim()}
          >
            {loading ? "Sending" : "Answer"}
          </button>
        </form>
      </div>
    </section>
  );
}
