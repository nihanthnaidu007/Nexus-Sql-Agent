/**
 * NIXUS SQL API client (Phase 8.1).
 *
 * Wired to the REAL, detected backend contract — nothing here is assumed:
 *
 *   Endpoint : POST /api/v1/run         (api/main.py:159 `@router.post("/run")`)
 *   Request  : { user_query, session_id?, clarification_context?, clarification_round? }
 *              (api/main.py:138 `class RunRequest`)
 *   Response : the raw final LangGraph state dict returned by run_query()
 *              (nixus/services/query_service.py:33 → nixus/graph/state.py:78 SQLAgentState)
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
  explanation: string;
  // Categorical confidence (nixus/graph/state.py:112-114)
  confidence: string | null; // "HIGH" | "MEDIUM" | "LOW"
  confidence_score: number;
  confidence_reasons: string[];
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

export interface RunRequest {
  user_query: string;
  session_id?: string;
  clarification_context?: unknown;
  clarification_round?: number;
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
  sql: string;
  rows: Record<string, unknown>[];
  columns: string[];
  rowCount: number;
  insight: string;
  confidence: string | null;
  confidenceReasons: string[];
  servedFromCache: boolean;
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

/** POST a question to the real /api/v1/run endpoint and await the full result. */
export async function runQuery(
  userQuery: string,
  sessionId = "",
): Promise<NormalizedResult> {
  const body: RunRequest = { user_query: userQuery, session_id: sessionId };

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

  return {
    outcome,
    isRefusal,
    isClarification,
    isAnswer,
    sql: raw.generated_sql ?? cache?.cached_sql ?? "",
    rows,
    columns,
    rowCount,
    insight: raw.explanation ?? "",
    confidence: raw.confidence ?? null,
    confidenceReasons: raw.confidence_reasons ?? [],
    servedFromCache: !!raw.served_from_cache,
    clarifyingQuestion: raw.clarifying_question ?? "",
    refusalReason: raw.reason ?? raw.scope_message ?? raw.explanation ?? "",
    errorText: raw.error ?? "",
    raw,
  };
}
