import type { NormalizedResult } from "@/lib/api";
import { renderMarkdown } from "@/lib/markdown";
import { SqlBlock } from "./SqlBlock";
import { ResultTable } from "./ResultTable";

/** Confidence as a small inline tag (kept simple for 8.2; full banner is 8.3). */
function Confidence({
  level,
  cached,
}: {
  level: string | null;
  cached: boolean;
}) {
  const norm = (level ?? "UNKNOWN").toUpperCase();
  const cls =
    norm === "HIGH"
      ? "conf-high"
      : norm === "MEDIUM"
        ? "conf-medium"
        : norm === "LOW"
          ? "conf-low"
          : "conf-unknown";
  return (
    <div className="meta-row">
      <span className={`conf ${cls}`}>
        <span className="dot" /> Confidence · {norm}
      </span>
      {cached && <span className="tag">cached</span>}
    </div>
  );
}

/**
 * Renders one response. The happy path (ANSWERED) is the designed experience:
 * SQL → result → insight → confidence, revealed top-to-bottom with a staggered
 * entrance. Refusal and clarification keep the minimal, non-crashing treatment
 * from 8.1 (8.3 designs them fully).
 */
export function ResultView({ result }: { result: NormalizedResult }) {
  // ---- Refusal (minimal; 8.3 styles fully) ----
  if (result.isRefusal) {
    return (
      <div className="notice refusal" role="status">
        <div className="notice-label">Refused · {result.outcome}</div>
        <div className="notice-body">
          {result.refusalReason || "The request was refused."}
        </div>
      </div>
    );
  }

  // ---- Clarification (minimal; 8.3 designs the round-trip) ----
  if (result.isClarification) {
    return (
      <div className="notice clarify" role="status">
        <div className="notice-label">Needs clarification</div>
        <div className="notice-body">
          {result.clarifyingQuestion || "Could you rephrase or add detail?"}
        </div>
      </div>
    );
  }

  // ---- Answer (the designed happy path) ----
  return (
    <div className="results">
      <section className="section s0">
        <span className="label">SQL</span>
        {result.sql ? (
          <SqlBlock sql={result.sql} />
        ) : (
          <div className="empty">No SQL was generated for this query.</div>
        )}
      </section>

      <section className="section s1">
        <span className="label">Result</span>
        <ResultTable
          columns={result.columns}
          rows={result.rows}
          rowCount={result.rowCount}
          cached={result.servedFromCache}
        />
      </section>

      {result.insight && (
        <section className="section s2">
          <span className="label">Insight</span>
          <div className="insight">{renderMarkdown(result.insight)}</div>
        </section>
      )}

      <section className="section s3">
        <Confidence level={result.confidence} cached={result.servedFromCache} />
      </section>
    </div>
  );
}

/** While /run is in flight — show the instrument is working (no frozen page). */
export function RunningState() {
  return (
    <div aria-live="polite">
      <div className="running">
        <span className="running-dot" />
        Running query…
      </div>
      <div className="skeleton" aria-hidden>
        <div className="bar w1" />
        <div className="bar w2" />
        <div className="bar w3" />
      </div>
    </div>
  );
}
