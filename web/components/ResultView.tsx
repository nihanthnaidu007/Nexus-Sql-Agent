import type { NormalizedResult } from "@/lib/api";
import { renderMarkdown } from "@/lib/markdown";
import { SqlBlock } from "./SqlBlock";
import { ResultTable } from "./ResultTable";
import { ConfidenceBanner } from "./ConfidenceBanner";

/**
 * The ANSWERED happy path: SQL → result → insight → confidence, revealed top to
 * bottom with a staggered entrance. Refusal and clarification are no longer
 * rendered here — they have dedicated, designed components (Refusal, Clarification)
 * driven by the page's conversation state.
 */
export function AnswerView({ result }: { result: NormalizedResult }) {
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
        <span className="label">Confidence</span>
        <ConfidenceBanner
          level={result.confidence}
          reasons={result.confidenceReasons}
          cached={result.servedFromCache}
        />
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
