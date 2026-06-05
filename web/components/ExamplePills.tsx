"use client";

/**
 * Example-question pills (Phase 13, B12). A restrained row of starter questions
 * for the SaaS SAMPLE schema (organizations, users, plans, subscriptions,
 * usage_events, invoices, payments). Clicking a pill FILLS the input — it does not
 * auto-submit, so the user stays in control and can tweak before running.
 *
 * The set is chosen to showcase RANGE: a plain count, group-by/chart-friendly
 * shapes, a join, and a time-based question — so a first-time visitor sees what the
 * tool can do without typing. Deliberately SaaS-flavored (not the Streamlit Chinook
 * "Top 5 artists…" examples), and styled in the warm-paper "Engineering Ledger"
 * language so they sit quietly under the input rather than dominating it.
 */

const EXAMPLES = [
  "How many active subscriptions are there?",
  "How many users does each organization have?",
  "Which plan has the most subscriptions?",
  "Show total payment revenue by month",
  "List the 10 organizations with the highest invoice totals",
  "Break down usage events by event type",
];

export function ExamplePills({
  onPick,
  disabled,
}: {
  onPick: (question: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="examples" aria-label="Example questions">
      <span className="examples-label">Try</span>
      <div className="examples-pills">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            type="button"
            className="example-pill"
            onClick={() => onPick(q)}
            disabled={disabled}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
