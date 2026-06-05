/**
 * Pipeline — the run's execution RECORD (Phase 11). Three read-only views over
 * the final /run state, all fields the backend already returns:
 *
 *   · NodeStatus    (B4, STATIC) — the graph's stages as calm badges showing each
 *                    node's FINAL state: done / skipped-by-cache / error / not-run.
 *   · CorrectionLog (B7)         — the self-correction attempts; EMPTY on a clean
 *                    first pass (the common case) → a positive "clean pass" line.
 *   · ExecutionLog  (B8)         — the per-node status lines the graph emitted.
 *
 * CRITICAL: this is the STATIC end-state — the query already ran; we render what it
 * DID. The LIVE animated node progression (running → done per node over SSE) is
 * Phase 12. Deliberately NOT Streamlit's neon node pulse: restrained ledger badges
 * in the established warm-paper / oxblood / hairline language. Emptiness is honest
 * and common — empty panels are omitted or shown as a positive signal, never a box.
 */
import type { CorrectionEntry, NormalizedResult, StreamUpdate } from "@/lib/api";

/**
 * The graph's nodes in execution order (nixus/graph/graph.py:99-112), with calm
 * human labels. `branch: true` marks the two CONDITIONAL nodes that a clean answer
 * path doesn't reach — scope_response (refusal/clarification only) and self_correct
 * (only when a query needs fixing) — so a "not-run" branch reads as design, not gap.
 */
const NODES: { key: string; label: string; branch?: boolean }[] = [
  { key: "scope_classifier", label: "Scope" },
  { key: "scope_response", label: "Scope reply", branch: true },
  { key: "parse_intent", label: "Parse intent" },
  { key: "check_cache", label: "Cache" },
  { key: "retrieve_schema", label: "Schema" },
  { key: "retrieve_fewshot", label: "Few-shot" },
  { key: "generate_sql", label: "Generate" },
  { key: "validate_syntax", label: "Validate" },
  { key: "verify_grounding", label: "Grounding" },
  { key: "execute_query", label: "Execute" },
  { key: "check_result", label: "Check result" },
  { key: "self_correct", label: "Self-correct", branch: true },
  { key: "classify_chart", label: "Chart" },
  { key: "explain_result", label: "Explain" },
];

const NODE_LABEL: Record<string, string> = Object.fromEntries(
  NODES.map((n) => [n.key, n.label]),
);

/**
 * The compute nodes a CACHE HIT short-circuits: on a hit, check_cache routes
 * straight to classify_chart (nixus/graph/graph.py:130-132), so retrieval →
 * generation → execution never run. Verified live: a cache hit's completed_nodes is
 * [scope_classifier, parse_intent, check_cache, classify_chart, explain_result],
 * leaving exactly these seven bypassed. We label them SKIPPED (CACHE), not done.
 */
const CACHE_BYPASS = new Set([
  "retrieve_schema",
  "retrieve_fewshot",
  "generate_sql",
  "validate_syntax",
  "verify_grounding",
  "execute_query",
  "check_result",
]);

type NodeState = "done" | "skip" | "error" | "idle";

const STATE_TAG: Partial<Record<NodeState, string>> = {
  skip: "cache",
  error: "error",
};

/**
 * STATIC node-status view (B4). Each of the 14 graph nodes, in order, in its FINAL
 * state derived from the completed/current/cache/error fields — no animation.
 */
function NodeStatus({ result }: { result: NormalizedResult }) {
  const completed = new Set(result.completedNodes);
  const cached = result.servedFromCache;
  const current = result.currentNode;
  // An actual run failure (not a refusal, which is a clean outcome) — used only to
  // mark the node the run halted at. Empty on every clean/cache path → never fires.
  const failed = result.errorText.trim().length > 0;

  function stateOf(key: string): NodeState {
    if (completed.has(key)) return "done"; // ran and finished (even after retries)
    if (failed && key === current) return "error"; // run halted here
    if (cached && CACHE_BYPASS.has(key)) return "skip"; // bypassed by the cache hit
    return "idle"; // a conditional branch this run didn't take
  }

  const corrections = result.correctionAttempts;

  return (
    <div className="nodes-wrap">
      <div className="nodes" role="list" aria-label="Pipeline stages">
        {NODES.map(({ key, label }) => {
          const state = stateOf(key);
          const tag = STATE_TAG[state];
          return (
            <span
              key={key}
              role="listitem"
              className={`node node-${state}`}
              title={`${label} — ${
                state === "done"
                  ? "completed"
                  : state === "skip"
                    ? "skipped (served from cache)"
                    : state === "error"
                      ? "run halted here"
                      : "not run on this path"
              }`}
            >
              <span className="node-dot" aria-hidden />
              <span className="node-name">{label}</span>
              {tag && <span className="node-tag">{tag}</span>}
            </span>
          );
        })}
      </div>
      {corrections > 0 && (
        <span className="nodes-note">
          {corrections} correction{corrections === 1 ? "" : "s"}
        </span>
      )}
    </div>
  );
}

/**
 * Self-correction log (B7). When the agent had to fix its own SQL, list each
 * attempt — what failed, the diagnosis, and the corrected query. EMPTY is the
 * COMMON case (clean first pass): we show a single quiet POSITIVE line, never an
 * empty expander. (correction_history shape: nixus/graph/nodes/self_correct.py.)
 */
function CorrectionLog({ history }: { history: CorrectionEntry[] }) {
  if (history.length === 0) {
    return (
      <p className="pipe-clean">
        <span className="pipe-clean-mark" aria-hidden />
        Answered on the first attempt — no self-correction needed.
      </p>
    );
  }

  return (
    <details className="expander" open>
      <summary className="expander-summary">
        Self-correction · {history.length} attempt
        {history.length === 1 ? "" : "s"}
      </summary>
      <ol className="correction-log">
        {history.map((c) => (
          <li className="correction-item" key={c.attempt}>
            <div className="correction-head">
              <span className="correction-attempt">Attempt {c.attempt}</span>
              {c.error_message && (
                <span className="correction-error">{c.error_message}</span>
              )}
            </div>
            {c.fix_reasoning && (
              <p className="correction-why">{c.fix_reasoning}</p>
            )}
            {c.corrected_sql && (
              <pre className="correction-sql">
                <code>{c.corrected_sql}</code>
              </pre>
            )}
          </li>
        ))}
      </ol>
    </details>
  );
}

/** node label + status → the human node name for an execution-log line. */
function execNodeLabel(node: string): string {
  return NODE_LABEL[node] ?? node;
}

/**
 * Agent execution log (B8). The per-node status lines the graph emitted — verified
 * POPULATED on the /run path. Collapsed by default (it's verbose and secondary).
 * status ∈ done | error | running → a calm status dot (not neon). If somehow empty,
 * the whole panel is omitted — we never draw an empty log or fabricate entries.
 */
function ExecutionLog({ updates }: { updates: StreamUpdate[] }) {
  if (updates.length === 0) return null;

  return (
    <details className="expander">
      <summary className="expander-summary">
        Execution log · {updates.length} step{updates.length === 1 ? "" : "s"}
      </summary>
      <ol className="exec-log">
        {updates.map((u, i) => (
          <li className={`exec-line exec-${u.status}`} key={`${u.node}-${i}`}>
            <span className="exec-time">{u.timestamp}</span>
            <span className="exec-node">{execNodeLabel(u.node)}</span>
            <span className="exec-msg">{u.message}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

/**
 * The Pipeline section: the static node record, then the self-correction log, then
 * the agent execution log. Subordinate to SQL / result / insight / confidence — it
 * answers "what did the pipeline do" at a glance, with the verbose logs on demand.
 */
export function PipelineSection({ result }: { result: NormalizedResult }) {
  // Nothing the graph reported → render nothing (shouldn't happen on a real /run).
  if (result.completedNodes.length === 0 && result.streamUpdates.length === 0) {
    return null;
  }

  return (
    <section className="section s4 pipeline">
      <span className="label">Pipeline</span>
      <NodeStatus result={result} />
      <CorrectionLog history={result.correctionHistory} />
      <ExecutionLog updates={result.streamUpdates} />
    </section>
  );
}
