/**
 * NIXUS SQL API client (Phase 8.1 → extended in 8.3).
 *
 * Wired to the REAL, detected backend contract — nothing here is assumed:
 *
 *   Endpoint : POST /api/v1/run         (api/main.py:159 `@router.post("/run")`)
 *   Request  : { user_query, session_id?, clarification_context?, clarification_round? }
 *              (api/main.py:138 `class RunRequest`)
 *   Response : the raw final LangGraph state dict returned by run_query()
 *              (nixus/services/query_service.py:33 → nixus/graph/state.py:78 SQLAgentState)
 *
 * 8.3 note: the CONTRACT is unchanged. The clarification round-trip added in 8.3
 * only POPULATES request fields the RunRequest model already declares
 * (session_id + clarification_context + clarification_round, api/main.py:138-144).
 * The folding rule is the backend's: clarification_context carries
 * {original_question, prior_clarifications:[{question, answer}]}, the latest answer
 * is ALSO echoed in user_query, and the server decides N=2 termination itself
 * (nixus/graph/scope.py: CLARIFICATION_ROUND_CAP=2). We send; the server decides.
 *
 * Streaming: the API DOES expose an SSE endpoint (POST /api/v1/stream, an
 * sse_starlette EventSourceResponse at api/main.py:174). 8.1 deliberately uses
 * the NON-streaming /api/v1/run instead: it returns the complete final state in a
 * single request/response — the minimal, most robust proof that the new frontend
 * reaches the proven backend. The incremental SSE/progress UI is 8.2's job; this
 * file leaves that endpoint untouched rather than half-building a stream client.
 *
 * Base URL: the BROWSER (running on the host) calls the API at http://localhost:8000.
 * The compose service name `api:8000` only resolves INSIDE the compose network, so
 * it must NOT be used from browser-side fetch. The default below is host-reachable;
 * CORS on the API already allows http://localhost:3000 (nixus/config.py:111).
 *
 * NEXT_PUBLIC_API_URL is inlined at BUILD time (Next.js public env), so compose
 * passes it as a build ARG (see web/Dockerfile + docker-compose.yml). If unset, the
 * default works for the standard one-command demo with no extra configuration.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---- The detected response shapes (subset 8.1 renders; full state is larger) ----

/** Live SQL execution result. NULL when the answer was served from cache. */
export interface ExecutionResult {
  success: boolean;
  rows: Record<string, unknown>[];
  columns: string[];
  row_count: number;
  execution_time_ms: number;
  error: string | null;
}

/** Semantic-cache hit. Carries its OWN rows under `result_preview`. */
export interface CacheResult {
  hit: boolean;
  similarity: number;
  cached_sql: string | null;
  result_preview: Record<string, unknown>[] | null;
  row_count?: number;
  chart_type?: string | null;
  explanation?: string | null;
  cache_id?: number | null;
}

/**
 * The chart the backend DECIDED for this result (nixus/graph/nodes/classify_chart.py).
 * The frontend RE-PLOTS from these primitives (chart_type + columns) over the result
 * rows; it deliberately does NOT parse `plotly_json`. That blob carries a neon-cyan
 * DARK theme (wrong for this warm-paper UI) and serializes integer y-values as a
 * binary typed array ({"dtype":"i1","bdata":"…"}) — re-plotting from the primitives
 * is both lighter and on-brand.
 *
 * chart_type observed live: "bar" | "line" | "pie" | "scatter" | "none". The
 * classifier picks line (date+numeric), pie (small positive distribution), bar
 * (categorical+numeric), scatter (≥2 numeric), or none (no/insufficient/unmappable
 * data). On the "none" path x/y/color are null and plotly_json is null.
 */
export type ChartType = "bar" | "line" | "pie" | "scatter" | "none";

export interface ChartConfig {
  chart_type: ChartType | string;
  x_column: string | null;
  y_column: string | null;
  color_column: string | null;
  title: string;
  reasoning: string;
  /** Present on the wire but intentionally unused by the renderer (see above). */
  plotly_json: string | null;
}

/**
 * One self-correction the agent made (nixus/graph/nodes/self_correct.py:89-95):
 * the SQL that failed, why it failed, the model's diagnosis, and the rewritten SQL.
 *
 * This list is EMPTY on a clean first-pass query — the COMMON case on this
 * benchmark (the graph answers most questions without ever entering self_correct).
 * The UI presents that empty case as a POSITIVE clean-pass signal, never an error.
 */
export interface CorrectionEntry {
  attempt: number;
  failed_sql: string;
  error_message: string;
  fix_reasoning: string;
  corrected_sql: string;
}

/**
 * One per-node status line the graph emits as it executes (the nodes append to
 * state["stream_updates"], e.g. nixus/graph/nodes/parse_intent.py:64-68). Verified
 * POPULATED on the /run path (not only /stream): a clean run returns ~12 entries,
 * a cache hit ~5. `status` is "done" | "error" | "running" across the nodes.
 */
export interface StreamUpdate {
  timestamp: string;
  node: string;
  message: string;
  status: string; // "done" | "error" | "running"
}

/**
 * The outcome discriminator (nixus/graph/scope.py:65-69). Every response carries
 * exactly one of these — it decides whether the UI shows an answer, a follow-up
 * question, or a refusal.
 */
export type Outcome =
  | "ANSWERED"
  | "NEEDS_CLARIFICATION"
  | "REFUSED_OUT_OF_SCOPE"
  | "REFUSED_WRITE"
  | "REFUSED_AMBIGUOUS";

/** The raw final graph state the API returns. Fields 8.1 reads are typed; the
 *  rest of the (large) state dict is preserved under the index signature. */
export interface NixusResponse {
  user_query: string;
  session_id: string;
  outcome: Outcome | null;
  // Answer path
  generated_sql: string;
  execution_result: ExecutionResult | null;
  cache_result: CacheResult | null;
  served_from_cache: boolean;
  // The backend's chart decision for this result (may be null on non-answer paths).
  chart_config: ChartConfig | null;
  explanation: string;
  // Categorical confidence (nixus/graph/state.py:112-114)
  confidence: string | null; // "HIGH" | "MEDIUM" | "LOW"
  confidence_score: number;
  confidence_reasons: string[];
  // Intelligence-strip fields (Phase 10) — what the system DID, surfaced read-only.
  // All already returned by /run (nixus/graph/state.py:91-105); normalize() used to
  // discard them. We do NOT change what is sent — only stop dropping what comes back.
  intent_class: string | null; // "READ" | "WRITE" | "SCHEMA_QUESTION" on the answer path
  extracted_entities: string[] | null; // entity strings (may be [] for simple queries)
  similar_examples: unknown[] | null; // few-shots loaded — we surface only the COUNT
  correction_attempts: number | null; // self-correction loops (0 = clean first pass; cap 3)
  // Execution record (Phase 11) — the pipeline's final end-state, all already
  // returned by /run (nixus/graph/state.py:115-121). The STATIC node view, the
  // self-correction log, and the agent execution log read these read-only.
  completed_nodes: string[]; // the nodes the graph actually traversed, in order
  current_node: string | null; // the last node touched (the failing node on error)
  is_complete: boolean; // did the run reach a terminal node
  correction_history: CorrectionEntry[]; // [] on a clean first pass (common case)
  stream_updates: StreamUpdate[]; // per-node log lines — populated on /run
  // Clarification path
  clarifying_question: string | null;
  // Refusal path
  reason: string | null;
  scope_message: string | null;
  // Diagnostics
  error: string | null;
  trace_url: string | null;
  [key: string]: unknown;
}

/** One clarification turn: the question the server asked + the user's answer. */
export interface ClarificationExchange {
  question: string;
  answer: string;
}

/** The stateless clarification round-trip carried back in on a follow-up
 *  (api/main.py:132 `class ClarificationContext`). */
export interface ClarificationContext {
  original_question: string;
  prior_clarifications: ClarificationExchange[];
}

export interface RunRequest {
  user_query: string;
  session_id?: string;
  clarification_context?: ClarificationContext;
  clarification_round?: number;
}

/** Options for threading a clarified follow-up into the SAME conversation. */
export interface RunOptions {
  sessionId?: string;
  clarificationContext?: ClarificationContext;
  clarificationRound?: number;
}

/** A normalized, UI-ready view derived from the raw response. The point of this
 *  layer is to hide the one real subtlety the backend has: answer rows live in
 *  `execution_result` on a live run but in `cache_result.result_preview` on a
 *  cache hit. The UI consumes `rows`/`columns`/`sql` without caring which. */
export interface NormalizedResult {
  outcome: Outcome | null;
  isRefusal: boolean;
  isClarification: boolean;
  isAnswer: boolean;
  // The server-assigned session id — threaded back on a clarified follow-up so the
  // conversation continues rather than starting fresh.
  sessionId: string;
  sql: string;
  rows: Record<string, unknown>[];
  columns: string[];
  rowCount: number;
  insight: string;
  confidence: string | null;
  confidenceReasons: string[];
  servedFromCache: boolean;
  // ---- Intelligence strip (Phase 10): what the system did + how confident -----
  // Render-only fields the backend already returns; kept here so the strip can
  // surface them. Absent/empty cases are represented HONESTLY (null / [] / 0), not
  // faked — the UI omits a field rather than drawing an empty box.
  intentClass: string | null; // READ | WRITE | SCHEMA_QUESTION (null → omit the badge)
  extractedEntities: string[]; // [] for simple queries → pills omitted
  fewShotCount: number; // count of similar_examples loaded (0 is meaningful)
  correctionAttempts: number; // self-correction loops (0 = clean first pass; cap 3)
  confidenceScore: number | null; // numeric score complementing the categorical level
  cacheHit: boolean; // cache_result.hit — the authoritative cache signal
  cacheSimilarity: number | null; // similarity ONLY when hit (0.0 on a miss → null)
  executionTimeMs: number | null; // live runs only; null when served from cache
  traceUrl: string | null; // LangSmith success-path trace; null when tracing is off
  // The backend's chart decision, carried through verbatim for ChartView to render.
  chartConfig: ChartConfig | null;
  // ---- Execution record (Phase 11): the STATIC end-state of the pipeline run ---
  // What the graph did, surfaced read-only for the node-status view, the self-
  // correction log, and the agent execution log. Emptiness is honest and common
  // (no corrections on a clean pass) — the UI omits empty panels, never fakes one.
  completedNodes: string[]; // nodes the graph traversed (DONE); cache hits skip some
  currentNode: string | null; // last node touched — the failing node on an error
  isComplete: boolean; // reached a terminal node
  correctionHistory: CorrectionEntry[]; // [] on a clean first pass (the common case)
  streamUpdates: StreamUpdate[]; // per-node log lines, populated on /run
  // Non-answer text
  clarifyingQuestion: string;
  refusalReason: string;
  errorText: string;
  // The full raw payload, for debugging / future phases.
  raw: NixusResponse;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly traceId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** POST a question to the real /api/v1/run endpoint and await the full result.
 *
 *  For a fresh query, call `runQuery(text)`. For a clarified follow-up, pass the
 *  threaded `opts` (the session id + accumulated clarification context + round) so
 *  the backend continues the SAME conversation. `userQuery` on a follow-up is the
 *  user's latest answer (the server also folds it via clarification_context). */
export async function runQuery(
  userQuery: string,
  opts: RunOptions = {},
): Promise<NormalizedResult> {
  const body: RunRequest = {
    user_query: userQuery,
    session_id: opts.sessionId ?? "",
  };
  if (opts.clarificationContext) {
    body.clarification_context = opts.clarificationContext;
    body.clarification_round = opts.clarificationRound ?? 0;
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/v1/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    // Network-level failure (API down, CORS blocked, DNS) — surface honestly.
    throw new ApiError(
      `Could not reach the API at ${API_BASE_URL}. Is the stack up? (${
        e instanceof Error ? e.message : String(e)
      })`,
    );
  }

  if (!res.ok) {
    // The API's global handler returns { error, trace_id, type } on 500.
    let detail = `${res.status} ${res.statusText}`;
    let traceId: string | undefined;
    try {
      const errBody = await res.json();
      if (errBody?.error) detail = String(errBody.error);
      if (errBody?.detail) detail += ` — ${errBody.detail}`;
      if (errBody?.trace_id) traceId = String(errBody.trace_id);
    } catch {
      /* response had no JSON body; keep the status line */
    }
    throw new ApiError(detail, res.status, traceId);
  }

  const data = (await res.json()) as NixusResponse;
  return normalize(data);
}

/** Collapse the raw graph state into the UI-ready shape. */
export function normalize(raw: NixusResponse): NormalizedResult {
  const outcome = raw.outcome ?? null;
  const isAnswer = outcome === "ANSWERED";
  const isClarification = outcome === "NEEDS_CLARIFICATION";
  const isRefusal = !!outcome && outcome.startsWith("REFUSED");

  // Rows + columns: prefer the live execution result; fall back to the cache hit.
  const exec = raw.execution_result;
  const cache = raw.cache_result;
  let rows: Record<string, unknown>[] = [];
  let columns: string[] = [];
  let rowCount = 0;

  if (exec && Array.isArray(exec.rows)) {
    rows = exec.rows;
    columns = exec.columns ?? [];
    rowCount = exec.row_count ?? rows.length;
  } else if (cache && Array.isArray(cache.result_preview)) {
    rows = cache.result_preview;
    rowCount = cache.row_count ?? rows.length;
  }
  // Derive columns from the first row when the backend didn't supply them
  // (the cache path carries rows but no explicit `columns` list).
  if (columns.length === 0 && rows.length > 0) {
    columns = Object.keys(rows[0]);
  }

  // Intelligence-strip fields — kept honest to the real shape from the live /run:
  //  · cache_result EXISTS on a miss too (hit:false, similarity:0.0) → only treat
  //    similarity as meaningful when hit, so the strip never shows a "0.0" score.
  //  · execution_result is null/absent on a cache hit → no timing to show.
  const cacheHit = !!cache?.hit;

  return {
    outcome,
    isRefusal,
    isClarification,
    isAnswer,
    sessionId: raw.session_id ?? "",
    sql: raw.generated_sql ?? cache?.cached_sql ?? "",
    rows,
    columns,
    rowCount,
    insight: raw.explanation ?? "",
    confidence: raw.confidence ?? null,
    confidenceReasons: raw.confidence_reasons ?? [],
    servedFromCache: !!raw.served_from_cache,
    intentClass: raw.intent_class ?? null,
    extractedEntities: Array.isArray(raw.extracted_entities)
      ? raw.extracted_entities
      : [],
    fewShotCount: Array.isArray(raw.similar_examples)
      ? raw.similar_examples.length
      : 0,
    correctionAttempts:
      typeof raw.correction_attempts === "number" ? raw.correction_attempts : 0,
    confidenceScore:
      typeof raw.confidence_score === "number" ? raw.confidence_score : null,
    cacheHit,
    cacheSimilarity:
      cacheHit && typeof cache?.similarity === "number" ? cache.similarity : null,
    executionTimeMs:
      typeof exec?.execution_time_ms === "number" ? exec.execution_time_ms : null,
    traceUrl: raw.trace_url ?? null,
    chartConfig: raw.chart_config ?? null,
    // Execution record — kept honest to the real shape: lists default to [] (never
    // null), so the views can treat "no data" as the clean/empty case uniformly.
    completedNodes: Array.isArray(raw.completed_nodes)
      ? raw.completed_nodes.filter((n): n is string => typeof n === "string")
      : [],
    currentNode: typeof raw.current_node === "string" ? raw.current_node : null,
    isComplete: !!raw.is_complete,
    correctionHistory: Array.isArray(raw.correction_history)
      ? (raw.correction_history as CorrectionEntry[])
      : [],
    streamUpdates: Array.isArray(raw.stream_updates)
      ? (raw.stream_updates as StreamUpdate[])
      : [],
    clarifyingQuestion: raw.clarifying_question ?? "",
    refusalReason: raw.reason ?? raw.scope_message ?? raw.explanation ?? "",
    errorText: raw.error ?? "",
    raw,
  };
}
