"use client";

import { useState } from "react";
import type { NormalizedResult } from "@/lib/api";
import { renderMarkdown } from "@/lib/markdown";
import { SqlBlock } from "./SqlBlock";
import { ResultTable } from "./ResultTable";
import { ChartView, hasChart } from "./ChartView";
import { ConfidenceBanner } from "./ConfidenceBanner";
import { IntelligenceStrip } from "./IntelligenceStrip";
import { PipelineSection } from "./Pipeline";

/**
 * The ANSWERED happy path: SQL → result → insight → confidence, revealed top to
 * bottom with a staggered entrance. Refusal and clarification are no longer
 * rendered here — they have dedicated, designed components (Refusal, Clarification)
 * driven by the page's conversation state.
 *
 * Phase 9: the Result section gains a Table ⇄ Chart toggle. The data table stays
 * the DEFAULT (it is the primary artifact); Chart is a view OVER the same already-
 * returned rows — switching never refetches. The chart itself is the backend's
 * decision (chart_config), re-plotted in this UI's language by ChartView.
 */

type ResultMode = "table" | "chart";

/** The Table ⇄ Chart segmented control, in the ledger language. */
function ViewToggle({
  mode,
  onMode,
  chartable,
}: {
  mode: ResultMode;
  onMode: (m: ResultMode) => void;
  chartable: boolean;
}) {
  return (
    <div className="view-toggle" role="group" aria-label="Result view">
      <button
        type="button"
        aria-pressed={mode === "table"}
        onClick={() => onMode("table")}
      >
        Table
      </button>
      <button
        type="button"
        aria-pressed={mode === "chart"}
        onClick={() => onMode("chart")}
        // Chart stays REACHABLE even when there's nothing to chart — opening it
        // shows the honest "no visualization" state rather than hiding the why.
        title={chartable ? "View as chart" : "No chart for this result shape"}
      >
        Chart
      </button>
    </div>
  );
}

/**
 * The result panel footer: run metrics + the success-path trace link.
 *
 *  · TIMING (B10): "{rows} rows · {ms} ms". The ms segment shows only on a live
 *    run — a cache hit has no execution_time_ms, so we omit it rather than fake a 0.
 *  · TRACE (B16): a subtle "view trace ↗" to LangSmith, rendered ONLY when the
 *    backend supplies trace_url (tracing on). When tracing is off (trace_url null)
 *    it is quietly omitted — never a dead link. (The ERROR-path trace handling in
 *    page.tsx is separate and untouched.)
 */
function ResultFooter({
  rowCount,
  executionTimeMs,
  traceUrl,
}: {
  rowCount: number;
  executionTimeMs: number | null;
  traceUrl: string | null;
}) {
  return (
    <div className="result-foot">
      <span className="result-foot-meta">
        {rowCount.toLocaleString()} row{rowCount === 1 ? "" : "s"}
        {executionTimeMs != null && (
          <>
            {" · "}
            {executionTimeMs} ms
          </>
        )}
      </span>
      {traceUrl && (
        <a
          className="trace-link"
          href={traceUrl}
          target="_blank"
          rel="noreferrer"
        >
          view trace ↗
        </a>
      )}
    </div>
  );
}

export function AnswerView({ result }: { result: NormalizedResult }) {
  const [mode, setMode] = useState<ResultMode>("table");
  const chartable = hasChart(result.chartConfig);

  return (
    <div className="results">
      {/* What the system DID — a glanceable header above the artifacts. */}
      <IntelligenceStrip result={result} />

      <section className="section s0">
        <span className="label">SQL</span>
        {result.sql ? (
          <SqlBlock sql={result.sql} />
        ) : (
          <div className="empty">No SQL was generated for this query.</div>
        )}
      </section>

      <section className="section s1">
        <div className="result-head">
          <span className="label">Result</span>
          <ViewToggle mode={mode} onMode={setMode} chartable={chartable} />
        </div>
        {mode === "table" ? (
          <ResultTable
            columns={result.columns}
            rows={result.rows}
            rowCount={result.rowCount}
            cached={result.servedFromCache}
          />
        ) : (
          <ChartView config={result.chartConfig} rows={result.rows} />
        )}
        <ResultFooter
          rowCount={result.rowCount}
          executionTimeMs={result.executionTimeMs}
          traceUrl={result.traceUrl}
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

      {/* The execution RECORD — what the pipeline did, end-state (Phase 11). Static,
          subordinate to the answer above; the LIVE node animation is Phase 12. */}
      <PipelineSection result={result} />
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
