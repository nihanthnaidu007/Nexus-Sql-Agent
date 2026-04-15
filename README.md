# ◈ NEXUS SQL — LangGraph Text-to-SQL Agent

A production-grade AI engineering project demonstrating an end-to-end Text-to-SQL pipeline. Built as a 12-node LangGraph state machine with pgvector semantic search, real-time SSE streaming, human-in-the-loop WRITE approval, self-correcting SQL generation, and automatic chart classification. Powered by Claude Haiku for intent parsing, Claude Sonnet for SQL generation and self-correction, and deployed as a live Streamlit UI over a FastAPI backend.

---

## Interface — Query Input & State Machine

![NEXUS SQL — Main interface showing query input, state machine, and generated SQL](images/image%201.png)

## Results — Table View with AI Insight

![NEXUS SQL — Table view with data results and AI-generated insight card](images/image%202.png)

## Results — Auto-Generated Chart View

![NEXUS SQL — Bar chart auto-generated from query results with LangSmith trace link](images/image%203.png)

---

## What This Project Demonstrates

This is not a prompt-wrapper demo. It covers the complete AI engineering pipeline from natural language to database result:

- **12-node LangGraph state machine** with conditional routing, self-correction loops, and interrupt/resume for human approval
- **pgvector semantic search** for schema retrieval, few-shot example retrieval, and semantic query caching — all using HNSW indexes
- **Fully async execution** — every node, database call, and LLM invocation is `async/await` with asyncpg
- **Server-Sent Events (SSE) streaming** — each node fires a real-time update visible in the UI before the full pipeline completes
- **LangSmith tracing** — every graph invocation produces a shareable trace URL with per-node latency and token counts
- **LangGraph interrupt() for WRITE approval** — stateful pause with MemorySaver checkpointing; resumes after human decision via `/api/approve-write`
- **Self-correcting SQL** — up to 3 correction attempts with Claude Sonnet diagnosing why the query failed and rewriting it
- **Auto chart classification** — heuristic column type detection automatically selects pie, bar, line, or scatter charts using Plotly
- **Edit SQL and re-run** — users can modify generated SQL in the UI and re-execute without re-running the full agent pipeline

---

## Architecture — 12-Node State Machine

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        LangGraph State Machine                      │
│                                                                     │
│  parse_intent ──► [READ?]──────────────────────► check_cache        │
│       │                                               │             │
│       └──► [WRITE?]──► safety_check ──[approved]──► check_cache    │
│                              │                        │             │
│                           [denied]            [HIT]   [MISS]        │
│                              │                  │       │           │
│                             END            classify  retrieve        │
│                                             _chart    _schema       │
│                                               │          │          │
│                                               │     retrieve        │
│                                               │    _fewshot         │
│                                               │          │          │
│                                               │    generate_sql     │
│                                               │          │          │
│                                               │   validate_syntax   │
│                                               │    │         │      │
│                                               │ [valid] [invalid]   │
│                                               │    │         │      │
│                                               │ execute  self       │
│                                               │  _query  _correct   │
│                                               │    │         │      │
│                                               │ check_result        │
│                                               │    │         │      │
│                                               │ [ok] [bad/empty]    │
│                                               │   │      │          │
│                                               ◄───┘  self_correct   │
│                                                    (max 3 attempts) │
│                                                         │           │
│                                               explain_result        │
│                                                         │           │
│                                                        END          │
└─────────────────────────────────────────────────────────────────────┘
```

### Node Descriptions

| Node | Model | Purpose |
|---|---|---|
| `parse_intent` | Claude Haiku 4.5 | Classifies query as READ / WRITE / SCHEMA_QUESTION / AMBIGUOUS; extracts key entities |
| `safety_check` | — | LangGraph `interrupt()` gate — blocks WRITE operations and waits for explicit human approval |
| `check_cache` | OpenAI text-embedding-3-small | Embeds query and searches pgvector cache with cosine similarity (threshold: 0.92) |
| `retrieve_schema` | OpenAI text-embedding-3-small | Semantic search over `schema_embeddings` table — retrieves top-K relevant table schemas |
| `retrieve_fewshot` | OpenAI text-embedding-3-small | Semantic search over `fewshot_examples` table — retrieves similar past query-SQL pairs |
| `generate_sql` | Claude Sonnet 4.5 | Generates PostgreSQL from natural language using retrieved schema + few-shot context |
| `validate_syntax` | sqlglot | Parses and normalizes SQL; detects parse errors without executing against the database |
| `execute_query` | asyncpg | Executes normalized SQL against Chinook PostgreSQL with configurable timeout and 1000-row cap |
| `check_result` | — | Evaluates result quality: GOOD / EMPTY / ERROR / OVERFLOW; routes to correction or chart |
| `self_correct` | Claude Sonnet 4.5 | Diagnoses failure reason, rewrites SQL; tracked up to 3 attempts with full correction history |
| `classify_chart` | Plotly / pandas | Classifies columns as date/numeric/categorical; auto-selects chart type; generates Plotly JSON |
| `explain_result` | Claude Haiku 4.5 | Writes a 2-3 sentence business-language insight; stores result to cache and few-shot store |

---

## Technical Stack

| Component | Technology |
|---|---|
| Orchestration | LangGraph 0.2+ with `StateGraph` and `MemorySaver` |
| LLM (intent, explain) | Claude Haiku 4.5 (`claude-haiku-4-5`) |
| LLM (generate, correct) | Claude Sonnet 4.5 (`claude-sonnet-4-5`) |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) |
| Vector Database | pgvector on PostgreSQL 16 with HNSW indexes |
| SQL Validation | sqlglot (dialect-aware PostgreSQL parser) |
| Database Driver | asyncpg (async) + psycopg2-binary (seed scripts only) |
| ORM Layer | SQLAlchemy 2.0 async engine |
| API Framework | FastAPI 0.115+ |
| Streaming | SSE via sse-starlette (Server-Sent Events) |
| UI Framework | Streamlit 1.40+ |
| Experiment Tracking | LangSmith (optional, via `LANGCHAIN_TRACING_V2`) |
| Charting | Plotly Express + `plotly.graph_objects` |
| Data Processing | pandas + numpy |
| Containerization | Docker + Docker Compose |
| Demo Database | Chinook (music store schema, PostgreSQL) |

---

## Database Layer — Three pgvector Tables

All three tables use HNSW indexes (`m=16, ef_construction=64`) for sub-millisecond cosine similarity search at scale.

### `schema_embeddings`
Stores semantic embeddings of each table's description and column definitions. When a query arrives, the top-K most relevant table schemas are retrieved and injected into the SQL generation prompt — the LLM never sees tables it does not need.

```sql
TABLE: schema_embeddings
  id                  SERIAL PRIMARY KEY
  table_name          TEXT UNIQUE
  description         TEXT
  columns_json        TEXT
  sample_values_json  TEXT
  embedding           vector(1536)          -- HNSW cosine index
```

### `fewshot_examples`
Stores natural language → SQL pairs. Seeded initially from hand-crafted examples; grows automatically as successful queries are stored by `explain_result_node`. Retrieved by cosine similarity and injected into generation prompts as few-shot context.

```sql
TABLE: fewshot_examples
  id                  SERIAL PRIMARY KEY
  natural_language    TEXT
  sql_query           TEXT
  tables_used         TEXT[]
  query_type          TEXT
  embedding           vector(1536)          -- HNSW cosine index
  success_count       INTEGER
  auto_learned        BOOLEAN
```

### `query_cache`
Stores complete query results for fast re-serving. When a new query is semantically similar enough (≥ 0.92 cosine similarity) to a cached query, the pipeline short-circuits after `check_cache`: schema retrieval, few-shot retrieval, SQL generation, validation, and execution are all skipped. The cached SQL, result preview, and AI explanation are served instantly. Cache statistics (entries, hits, hit rate) appear in the UI bottom status bar.

```sql
TABLE: query_cache
  id                  SERIAL PRIMARY KEY
  user_query          TEXT
  query_embedding     vector(1536)          -- HNSW cosine index
  generated_sql       TEXT
  result_preview_json TEXT
  row_count           INTEGER
  chart_type          TEXT
  explanation         TEXT
  hit_count           INTEGER
  last_accessed       TIMESTAMPTZ
```

---

## Repository Structure

```
nexus-sql-agent/
├── api/
│   └── main.py                    # FastAPI app — /api/run, /api/stream, /api/approve-write,
│                                  # /api/run-sql, /api/health, /api/cache-stats,
│                                  # /api/fewshot-stats
├── db/
│   ├── connection.py              # Async + sync SQLAlchemy engines; Neon SSL support
│   ├── schema_store.py            # pgvector schema embedding search
│   ├── fewshot_store.py           # pgvector few-shot retrieval + auto-learning
│   └── query_cache.py             # pgvector semantic cache + hit tracking
├── graph/
│   ├── graph.py                   # LangGraph StateGraph builder; MemorySaver; interrupt_before
│   ├── state.py                   # SQLAgentState TypedDict + Pydantic result models
│   └── nodes/
│       ├── parse_intent.py        # Claude Haiku structured output: intent + entities
│       ├── check_cache.py         # pgvector cache lookup + hit increment
│       ├── retrieve_schema.py     # pgvector schema retrieval (top-K)
│       ├── retrieve_fewshot.py    # pgvector few-shot retrieval
│       ├── generate_sql.py        # Claude Sonnet SQL generation with schema + few-shot context
│       ├── validate_syntax.py     # sqlglot parse + normalize; CANNOT_ANSWER handling
│       ├── execute_query.py       # asyncpg execution with timeout + 1000-row cap
│       ├── check_result.py        # Result quality: GOOD / EMPTY / ERROR / OVERFLOW
│       ├── self_correct.py        # Claude Sonnet SQL debugging + rewrite (up to 3x)
│       ├── classify_chart.py      # Column type detection + Plotly figure generation
│       └── explain_result.py      # Claude Haiku insight + cache store + few-shot store
├── safety/
│   └── guardrails.py              # safety_check_node — approves or blocks WRITE operations
├── scripts/
│   ├── init_db.py                 # Idempotent DB setup: pgvector extension + all tables
│   ├── seed_schema_embeddings.py  # Embeds and stores Chinook table descriptions
│   ├── seed_fewshot_examples.py   # Seeds initial query-SQL training examples
│   ├── chinook_postgres.sql       # Full Chinook schema + data (PostgreSQL dialect)
│   └── entrypoint.sh              # Docker entrypoint: init → seed → start API → start UI
├── ui/
│   └── app.py                     # Streamlit UI: streaming handler, chart toggle,
│                                  # SQL editor, WRITE approval modal, LangSmith links
├── utils/
│   ├── embeddings.py              # OpenAI embedding wrapper (text-embedding-3-small)
│   ├── confidence.py              # Confidence score calculator from quality signals
│   ├── sql_formatter.py           # SQL syntax highlighting for UI
│   └── langsmith_config.py        # RunnableConfig builder + shareable trace URL
├── eval/                          # Evaluation harness (deepeval)
├── images/                        # Screenshots
├── Dockerfile                     # Python 3.13-slim; installs requirements
├── docker-compose.yml             # db (pgvector/pg16) + api + ui services
├── requirements.txt               # All Python dependencies
├── start.sh                       # Local dev: init → seed → uvicorn + streamlit
└── .env.example                   # Environment variable template
```

---

## Setup & Usage

### Prerequisites

- Python 3.11+ (tested on 3.13)
- Docker and Docker Compose (recommended)
- Anthropic API key
- OpenAI API key (for embeddings)
- PostgreSQL 16 with pgvector extension (provided via Docker)

### Option A — Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone <repo-url>
cd nexus-sql-agent

# 2. Create environment file
cp .env.example .env
# Edit .env with your API keys (see Environment Variables section below)

# 3. Start everything (database + API + UI)
docker-compose up --build

# Services start on:
#   API:  http://localhost:8000
#   UI:   http://localhost:8501
```

The Docker entrypoint automatically:
1. Creates the pgvector extension and all three vector tables
2. Seeds schema embeddings for all 11 Chinook tables
3. Seeds initial few-shot examples
4. Starts FastAPI on port 8000
5. Starts Streamlit on port 8501

### Option B — Local Development

```bash
# 1. Start only the database
docker-compose up db -d

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env with your credentials

# 5. Initialize database and seed data
python scripts/init_db.py
python scripts/seed_schema_embeddings.py
python scripts/seed_fewshot_examples.py

# 6. Start API and UI
./start.sh

# Or manually in two terminals:
uvicorn api.main:app --port 8000 --reload
streamlit run ui/app.py --server.port 8501
```

### Using a Remote PostgreSQL Database (Neon, Supabase, etc.)

Set `DATABASE_URL` in `.env` to a full connection string with `sslmode=require`. The connection layer automatically handles SSL configuration for both asyncpg and psycopg2 drivers:

```
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

---

## Environment Variables

Create a `.env` file from `.env.example` and fill in the following:

```bash
# ── Required ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...           # Claude Haiku (intent/explain) + Claude Sonnet (SQL/correct)
OPENAI_API_KEY=sk-...                  # text-embedding-3-small (1536-dim embeddings)
DATABASE_URL=postgresql://nexus:nexus@localhost:5432/nexus_sql

# ── Optional — LangSmith Tracing ────────────────────────────────────────────
LANGCHAIN_TRACING_V2=true              # Enable LangSmith tracing
LANGCHAIN_API_KEY=ls__...             # LangSmith API key
LANGCHAIN_PROJECT=nexus-sql            # Project name in LangSmith

# ── Optional — Tuning ───────────────────────────────────────────────────────
CACHE_SIMILARITY_THRESHOLD=0.92        # Cosine similarity threshold for cache hits (0.0–1.0)
SCHEMA_RETRIEVAL_TOP_K=6               # Number of schema tables retrieved per query
MAX_CORRECTION_ATTEMPTS=3              # Max self-correction attempts before routing to explain
QUERY_EXECUTION_TIMEOUT_SECONDS=10     # Per-query timeout for asyncpg execution
```

---

## API Reference

All endpoints are served by FastAPI at `http://localhost:8000`.

### `POST /api/run`
Synchronous full-pipeline run. Blocks until complete.

```json
Request:  { "user_query": "top 5 artists by total revenue", "session_id": "..." }
Response: { full SQLAgentState — generated_sql, execution_result, chart_config,
            explanation, confidence_score, correction_history, trace_url, ... }
```

### `POST /api/stream`
SSE streaming run. Fires one `node_complete` event per node, then a final `complete` event.

```
Request:  POST /api/stream  { "user_query": "...", "session_id": "..." }

Events:
  event: node_complete   data: { node, completed_nodes, stream_updates, intent_class, ... }
  event: interrupted     data: { node: "interrupted", requires_approval: true, write_operation_type }
  event: complete        data: { is_complete: true, generated_sql, execution_result,
                                 chart_config, explanation, trace_url, ... }
  event: error           data: { error: "...", is_complete: true }
```

### `POST /api/approve-write`
Resume a WRITE pipeline that was interrupted at `safety_check`.

```json
Request:  { "session_id": "abc-123", "approved": true }
Response: { "status": "approved", "generated_sql": "...", "execution_result": { ... }, ... }
```

### `POST /api/run-sql`
Execute user-edited SQL directly — skips generation, runs validate → execute → check → chart.

```json
Request:  { "sql": "SELECT ...", "session_id": "..." }
Response: { validation_result, execution_result, chart_config }
```

### `GET /api/health`
Health check for all subsystems.

```json
{
  "status": "ok",
  "db_connected": true,
  "embedding_api": true,
  "llm_api": true,
  "langsmith_tracing": false,
  "nodes": ["parse_intent", "safety_check", "check_cache", "retrieve_schema",
            "retrieve_fewshot", "generate_sql", "validate_syntax", "execute_query",
            "check_result", "self_correct", "classify_chart", "explain_result"],
  "version": "1.0.0"
}
```

### `GET /api/cache-stats`
Returns cache entry count, total hits, and hit rate percentage.

### `GET /api/fewshot-stats`
Returns total few-shot count, seeded count, and auto-learned count.

---

## Features In Detail

### Real-Time SSE Streaming

The `/api/stream` endpoint uses Server-Sent Events to push one event per node as soon as it completes. The Streamlit UI renders a live state-machine badge panel and an intelligence strip that update in real time — the user sees `parse_intent → check_cache → retrieve_schema` firing sequentially before the full result arrives.

### Semantic Query Cache

Every successful query is embedded and stored in `query_cache`. On subsequent queries with ≥ 0.92 cosine similarity, the pipeline short-circuits after `check_cache`: schema retrieval, few-shot retrieval, SQL generation, validation, and execution are all skipped. The cached SQL, result preview, and AI explanation are served instantly. Cache statistics (entries, hits, hit rate) appear in the bottom status bar.

### Human-in-the-Loop WRITE Approval

When `parse_intent` classifies a query as WRITE (INSERT, UPDATE, DELETE, DROP), LangGraph pauses execution at `safety_check` using `interrupt_before`. The UI shows an approval modal with the operation type. Clicking APPROVE or DENY calls `/api/approve-write`, which uses `Command(update={...}, resume=...)` to resume or terminate the stateful checkpoint. The same `MemorySaver` instance handles both the initial interrupt and the resume, preserving full graph state across the pause.

### Self-Correcting SQL

When `execute_query` fails or `check_result` classifies the result as EMPTY or ERROR, the graph routes to `self_correct_node`. Claude Sonnet receives the original question, the failed SQL, the failure reason, and all prior correction attempts, then produces a JSON response with diagnosis and corrected SQL. Up to 3 correction attempts are made before routing to `explain_result`. The full correction history is shown in the UI as an expandable self-correction log.

### Auto Chart Classification

`classify_chart_node` uses heuristic column type detection on the result DataFrame:
- Columns with name keywords (`date`, `time`, `year`, `month`, `created`, `updated`) → date columns
- Columns where ≥ 80% of sampled values are numeric → numeric columns
- Everything else → categorical columns

Chart type selection logic:

| Column Combination | Chart Type |
|---|---|
| date + numeric | line |
| categorical + numeric, ≤ 8 unique and ≤ 10 rows | pie |
| categorical + numeric, otherwise | bar |
| two numeric columns | scatter |

The figure is serialized to a custom JSON format that avoids Plotly's binary typed-array encoding (orjson compatibility issue), then deserialized in the UI using a custom base64 decoder.

### Auto-Learning Few-Shot Store

Every query that completes with zero corrections and a GOOD result quality is automatically stored in `fewshot_examples` with its natural language + SQL pair. These accumulate over time and improve future SQL generation quality without any manual curation. The count of auto-learned examples appears in the UI bottom status bar.

### LangSmith Tracing

When `LANGCHAIN_TRACING_V2=true`, every graph invocation is traced in LangSmith with per-node latency, token counts, and structured metadata. The `explain_result` node surfaces a shareable trace URL in the insight card footer and in the bottom status bar. The URL uses `?poll=true` so it loads even before the run finishes uploading.

---

## Demo Database — Chinook

The system runs against the [Chinook music store database](https://github.com/lerocha/chinook-database) (PostgreSQL dialect). Chinook is a realistic relational schema with 11 tables and approximately 4,800 rows of real music store data.

| Table | Rows | Description |
|---|---|---|
| `Artist` | 275 | Recording artists |
| `Album` | 347 | Albums linked to artists |
| `Track` | 3,503 | Tracks with genre, media type, duration, unit price |
| `Genre` | 25 | Music genres |
| `MediaType` | 5 | Media formats (MP3, AAC, MPEG, etc.) |
| `Playlist` | 18 | Curated playlists |
| `PlaylistTrack` | 8,715 | Many-to-many track-playlist mapping |
| `Customer` | 59 | Customers across 24 countries |
| `Invoice` | 412 | Customer invoices |
| `InvoiceLine` | 2,240 | Individual invoice line items |
| `Employee` | 8 | Employees with management hierarchy |

**Important:** All table and column names are PascalCase and must be double-quoted in PostgreSQL (`"Artist"`, `"TrackId"`, `"InvoiceLine"`). The SQL generation prompt enforces this with explicit rules and correction examples.

### Example Queries the System Handles

```
"Top 5 artists by total revenue"
"Which genre makes the most money per track?"
"Monthly invoice totals by country"
"Tracks longer than 5 minutes"
"Average track length by genre"
"Which playlists have the most tracks?"
"Customers by country"
"DELETE FROM Artist WHERE ArtistId = 999"   ← triggers WRITE approval flow
```

---

## Example Output

**Query:** `Which genre makes the most money per track?`

**Generated SQL:**
```sql
SELECT
  g."Name" AS genre_name,
  SUM(il."UnitPrice" * il."Quantity") / COUNT(DISTINCT t."TrackId") AS revenue_per_track
FROM "Genre" g
  JOIN "Track" t ON g."GenreId" = t."GenreId"
  JOIN "InvoiceLine" il ON t."TrackId" = il."TrackId"
GROUP BY g."GenreId", g."Name"
ORDER BY revenue_per_track DESC
LIMIT 1000
```

**AI Insight:**
> Science Fiction is your top performer, generating $2.39 in revenue per track — outpacing the second-place Comedy genre by about 7%. The top five genres are all relatively close in revenue per track (ranging from $1.99 to $2.39), suggesting that genre choice alone isn't a major revenue driver; other factors like pricing strategy or sales volume likely matter more.

**Chart:** Auto-classified as BAR (genre_name = categorical, revenue_per_track = numeric, 24 rows > 10 threshold for pie). Plotly figure generated server-side and rendered client-side with transparent dark theme.

---

## Self-Correction Prompt Design

When SQL fails, `self_correct_node` sends Claude Sonnet a structured debugging prompt that includes the full prior attempt history so it cannot repeat the same mistake:

```
ORIGINAL QUESTION: {user_query}

DATABASE SCHEMA:
{schema_context}

CRITICAL REMINDER: ALL table and column names use PascalCase and MUST be
double-quoted in PostgreSQL.
  Correct: "Artist", "ArtistId", "Track"
  Wrong:   Artist, artist, ArtistId (any unquoted form)

FAILED SQL (attempt {attempt}):
{failed_sql}

FAILURE REASON:
{failure_reason}

ALL PRIOR ATTEMPTS:
{correction_history}

Respond ONLY with this JSON. No markdown, no backticks:
{
  "fix_reasoning": "1-2 sentence diagnosis of exactly why it failed and what you changed",
  "corrected_sql": "SELECT ... the fixed SQL here"
}
```

---

## Query Intelligence Panel

The UI shows a real-time intelligence strip alongside the state machine:

| Signal | Source Node | Description |
|---|---|---|
| **Intent** | `parse_intent` | READ / WRITE / SCHEMA_QUESTION badge |
| **Cache** | `check_cache` | HIT (with cosine similarity score) or MISS |
| **Entities** | `parse_intent` | Key concepts extracted from the query |
| **Few-shots** | `retrieve_fewshot` | Number of similar past examples retrieved |
| **Corrections** | `self_correct` | N/3 correction attempts used |
| **Confidence** | `explain_result` | Score from 0–100% based on quality signals |

Confidence is computed from: correction attempts used, result quality status (GOOD / EMPTY / ERROR), syntax warnings, whether served from cache, and cache similarity score.

---

## Verification Checks

After any code change, run these checks to verify the system is intact:

```bash
# Check 1 — All Python files parse cleanly
python -c "
import ast, os
errors = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ['.git','__pycache__','.venv']]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try: ast.parse(open(path).read())
            except SyntaxError as e: errors.append(f'{path}: {e}')
print('All files parse cleanly' if not errors else '\n'.join(errors))
"

# Check 2 — Graph compiles with correct routing
python -c "
from dotenv import load_dotenv; load_dotenv()
from graph.graph import build_graph
g = build_graph()
print('Checkpointer:', type(g.checkpointer).__name__)
print('Nodes:', list(g.get_graph().nodes.keys()))
"

# Check 3 — Chart classification test (expects chart_type: pie, plotly_json length > 500)
python -c "
import asyncio, sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from graph.nodes.classify_chart import classify_chart_node

state = {
    'execution_result': {
        'success': True,
        'rows': [{'Name': 'Iron Maiden', 'TotalRevenue': 138.6},
                 {'Name': 'U2', 'TotalRevenue': 105.93},
                 {'Name': 'Metallica', 'TotalRevenue': 90.09},
                 {'Name': 'Led Zeppelin', 'TotalRevenue': 86.13},
                 {'Name': 'Lost', 'TotalRevenue': 81.59}],
        'columns': ['Name', 'TotalRevenue'],
        'row_count': 5, 'execution_time_ms': 7.0, 'error': None
    },
    'served_from_cache': False, 'cache_result': None,
    'current_node': '', 'completed_nodes': [], 'stream_updates': []
}
result = asyncio.run(classify_chart_node(state))
cc = result.get('chart_config') or {}
print('Chart type:', cc.get('chart_type'))
print('Has plotly_json:', bool(cc.get('plotly_json')))
print('plotly_json length:', len(cc.get('plotly_json') or ''))
"

# Check 4 — Health endpoint
curl http://localhost:8000/api/health
```

---

## Known Limitations

| Area | Limitation |
|---|---|
| Database | Hardcoded to Chinook — schema embeddings are Chinook-specific; switching databases requires re-seeding |
| Cache threshold | 0.92 cosine similarity is conservative — minor query variations may miss the cache |
| Self-correction | Limited to 3 attempts; complex multi-join queries with obscure failure modes may exhaust corrections |
| Chart detection | Heuristic-based; does not use LLM reasoning — unusual column naming conventions may misclassify chart type |
| WRITE sessions | Only one WRITE approval session active per `session_id` at a time; MemorySaver is in-memory and resets on restart |
| Streaming | SSE connection held open during full pipeline execution; aggressive proxy timeouts may interrupt long queries |

---

## Future Improvements

- **Multi-database support** — parameterize schema seeding to work with any PostgreSQL schema, not just Chinook
- **Agentic tool use** — replace the fixed node chain with a tool-calling agent that calls schema lookup and SQL execution dynamically
- **RLHF feedback loop** — thumbs up/down on query results to score and filter auto-learned few-shot examples
- **Redis session backend** — replace in-memory `MemorySaver` with Redis for multi-instance WRITE approval and persistent sessions
- **Evaluation harness** — deepeval integration in `eval/` for automated accuracy and SQL correctness benchmarking
- **User authentication** — per-user session isolation and query history

---

## Author

**Nihanth Naidu Kalisetti**
AI/ML Engineer · Graduate Student · Long Island University

---

## License

MIT License © 2026 Nihanth Naidu Kalisetti
