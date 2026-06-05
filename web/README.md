# NIXUS SQL — Web frontend (Phase 8)

Next.js (App Router) React frontend for NIXUS SQL.

**8.1 scope (this commit):** the minimum that proves integration — a single page,
a typed API client against the real backend, and one bare end-to-end round trip.
No query-UI polish, no trust-model display, no styling beyond readability. Those
are 8.2 and 8.3.

## The backend contract this client targets

Detected from `api/main.py` + a live `curl` (not assumed):

| | |
|---|---|
| Endpoint | `POST /api/v1/run` (non-streaming) |
| Request | `{ user_query: string, session_id?: string, clarification_context?, clarification_round? }` |
| Response | the raw final LangGraph state dict (`outcome`, `generated_sql`, `execution_result`, `cache_result`, `explanation`, `confidence`, `confidence_reasons`, `clarifying_question`, `reason`, `error`, …) |
| Outcome values | `ANSWERED`, `NEEDS_CLARIFICATION`, `REFUSED_OUT_OF_SCOPE`, `REFUSED_WRITE`, `REFUSED_AMBIGUOUS` |

The API *also* exposes an SSE endpoint (`POST /api/v1/stream`). 8.1 uses the
non-streaming `/api/v1/run` on purpose — it returns the complete result in one
request, the simplest robust proof of integration. The incremental SSE/progress UI
is 8.2.

One real subtlety the client normalizes: answer rows live in `execution_result.rows`
on a live run, but in `cache_result.result_preview` on a cache hit (where
`execution_result` is `null`). See `lib/api.ts` → `normalize()`.

## Local dev

```bash
npm install
npm run dev        # http://localhost:3000  (calls the API at http://localhost:8000)
```

`NEXT_PUBLIC_API_URL` overrides the API base URL (default `http://localhost:8000`).
The browser runs on the host, so it must use `localhost:8000`, **not** the compose
service name `api:8000` (that only resolves inside the compose network). CORS on the
API already allows `http://localhost:3000`.

## In docker-compose

Built as the `web` service: `docker compose up -d --build` then open
`http://localhost:3000`. The Streamlit `ui` service is left present-but-unused in
8.1 and is retired in 8.3.
