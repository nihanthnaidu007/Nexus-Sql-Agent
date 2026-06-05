"use client";

import { useRef } from "react";

/**
 * The natural-language question field. A flat, bordered command field with a
 * leading prompt glyph and a submit button — not a rounded pill. Enter submits;
 * Shift+Enter inserts a newline. Disabled + relabeled while a request is running.
 */
export function QueryForm({
  value,
  onChange,
  onSubmit,
  loading,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  }

  return (
    <section className="query">
      <span className="label" id="q-label">
        Ask the database
      </span>
      <div style={{ height: 14 }} />
      <form
        className="query-field"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <span className="query-prompt" aria-hidden>
          ›
        </span>
        <textarea
          ref={ref}
          className="query-input"
          aria-labelledby="q-label"
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="e.g. which organization has the most users?"
          disabled={loading}
        />
        <button className="query-submit" type="submit" disabled={loading || !value.trim()}>
          {loading ? "Running" : "Run"}
        </button>
      </form>
      <div className="query-hint">
        <kbd>Enter</kbd> to run · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line
      </div>
    </section>
  );
}
