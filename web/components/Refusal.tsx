/**
 * Refusal states — designed as DELIBERATE, legitimate outcomes, not errors.
 *
 * The product thesis is "trust over capability": declining is the system working
 * CORRECTLY (it refused rather than fabricated). So these are calm and confident —
 * no alarm color, no traceback, no SQL, no apology-as-error. They are visually
 * distinct from the real error path (an actual request failure), which is styled
 * separately in page.tsx with role="alert".
 *
 * Each REFUSED_* outcome gets its own framing: WHAT was declined and WHY.
 */
import type { Outcome } from "@/lib/api";

const FRAMING: Record<
  string,
  { kicker: string; headline: string; note: string }
> = {
  REFUSED_WRITE: {
    kicker: "Read-only by design",
    headline: "NIXUS doesn’t modify data.",
    note: "It can query and analyze, but never insert, update, or delete. This is a deliberate guarantee, not a limitation it hit.",
  },
  REFUSED_OUT_OF_SCOPE: {
    kicker: "Outside what this answers",
    headline: "That isn’t a question about this database.",
    note: "NIXUS answers questions about the data it holds. It declined rather than invent an answer.",
  },
  REFUSED_AMBIGUOUS: {
    kicker: "Couldn’t disambiguate",
    headline: "Still not specific enough to answer well.",
    note: "After asking for clarification, the intent stayed ambiguous — so NIXUS stopped rather than guess. Try a new question that names the table, metric, or filter.",
  },
};

export function Refusal({
  outcome,
  reason,
}: {
  outcome: Outcome | null;
  reason: string;
}) {
  const frame =
    (outcome && FRAMING[outcome]) ?? FRAMING.REFUSED_OUT_OF_SCOPE;

  return (
    <section className="refusal" role="status" aria-label="Request declined">
      <div className="refusal-kicker">{frame.kicker}</div>
      <h2 className="refusal-headline">{frame.headline}</h2>
      {/* The real reason field from the backend — the specific "why" for this input. */}
      {reason && <p className="refusal-reason">{reason}</p>}
      <p className="refusal-note">{frame.note}</p>
    </section>
  );
}
