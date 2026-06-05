#!/usr/bin/env bash
# ============================================================================
# 7.2 — First-run orchestration for the SELF-CONTAINED SaaS demo (the app image).
#
# Brings the stack up CORRECT on a clean start with no manual intervention, in a
# strict, idempotent order. Each step is safe to re-run on restart.
#
#   1. Wait for Postgres (state_db) to accept connections.
#   2. Apply state_db migrations (nixus/db/migrations).
#   3. Ensure the SaaS target is loaded + seeded (the DB init scripts do this on a
#      fresh volume; this is an idempotent safety net for existing volumes).
#   4. FAIL FAST if the required API keys are missing, then embed the target
#      schema (schema_embeddings) — embeddings need a live call; they can't be
#      precomputed, so a missing key fails fast instead of booting broken.
#   5. Start the API.
#
# This script NEVER runs `docker compose down -v`. Teardown is the user's action.
# ============================================================================
set -euo pipefail

echo "◈ [1/5] Waiting for Postgres (state_db) to accept connections..."
python - <<'PYEOF'
import asyncio, os, sys, time
from dotenv import load_dotenv
load_dotenv(os.path.join(os.getcwd(), ".env"))
from nixus.db.connection import check_db_connection
for attempt in range(1, 31):
    try:
        if asyncio.run(check_db_connection()):
            print(f"  ✓ database ready (attempt {attempt})"); sys.exit(0)
    except Exception:
        pass
    print(f"  attempt {attempt}/30 — retrying in 2s..."); time.sleep(2)
print("✗ database did not become ready after 60s"); sys.exit(1)
PYEOF

echo "◈ [2/5] Applying state_db migrations (nixus/db/migrations)..."
python - <<'PYEOF'
import os; from dotenv import load_dotenv; load_dotenv(os.path.join(os.getcwd(), ".env"))
from nixus.db.migrations.runner import apply_migrations_sync
applied = apply_migrations_sync()
print(f"  ✓ migrations: {applied if applied else 'already up to date'}")
PYEOF

echo "◈ [3/5] Ensuring the SaaS sample target is loaded + seeded (idempotent)..."
python - <<'PYEOF'
import sys, subprocess
import os; from dotenv import load_dotenv; load_dotenv(os.path.join(os.getcwd(), ".env"))
from nixus.config import settings

target_db = (settings.target_url or "").rsplit("/", 1)[-1].split("?")[0]
# Map each bundled sample target to its deterministic rebuild script. The DEMO
# (nixus_saas_demo) is the stack default; nixus_saas is the FROZEN benchmark set.
# Both rebuild scripts target their OWN database only — never each other's.
REBUILD = {
    "nixus_saas_demo": "scripts/rebuild_demo_db.py",
    "nixus_saas": "scripts/rebuild_saas_db.py",
}

def target_table_count() -> int:
    """Owner-connection count of public tables in the target (−1 if unknown)."""
    admin = settings.target_admin_url or ""
    if not admin:
        return -1
    try:
        import psycopg2
        conn = psycopg2.connect(admin)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
            n = cur.fetchone()[0]
        conn.close()
        return int(n)
    except Exception as e:
        print(f"  (could not inspect target: {type(e).__name__}) — assuming present")
        return -1

def flush_query_cache() -> None:
    """Discard query_cache after a FRESH target build — cached results (SQL +
    row preview) are target-specific, and a just-built target has no legitimate
    cache. This keeps the demo correct on the realistic upgrade path (an existing
    state volume where the default target changed, so the new target is built on
    first boot). On a truly fresh volume the cache is already empty (no-op)."""
    state = settings.state_url or settings.database_url or ""
    if not state:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(state); conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.query_cache')")
            if cur.fetchone()[0] is not None:
                cur.execute("DELETE FROM query_cache")
                print(f"  ✓ flushed query_cache ({cur.rowcount} stale entries) after fresh build")
        conn.close()
    except Exception as e:
        print(f"  (could not flush query_cache: {type(e).__name__}) — continuing")

n = target_table_count()
rebuild = REBUILD.get(target_db)
if rebuild and n == 0:
    # Fresh-volume init normally already loaded this target; rebuild only if empty.
    print(f"  target {target_db} is empty — building it via {rebuild} ...")
    subprocess.run([sys.executable, rebuild], check=True)
    flush_query_cache()
else:
    shown = n if n >= 0 else "unknown"
    print(f"  ✓ target already provisioned ({shown} public tables) — skipping")
PYEOF

echo "◈ [4/5] Embedding prep — checking required API keys (fail fast)..."
python - <<'PYEOF'
import sys
import os; from dotenv import load_dotenv; load_dotenv(os.path.join(os.getcwd(), ".env"))
from nixus.config import settings

def missing(v: str | None) -> bool:
    return (not v) or v.strip() == "" or v.strip().lower().startswith("your_")

problems = []
if missing(settings.openai_api_key):
    problems.append("OPENAI_API_KEY  (schema embeddings — required to introspect the target)")
if missing(settings.anthropic_api_key):
    problems.append("ANTHROPIC_API_KEY  (the agent LLM — required to answer queries)")

if problems:
    print("✗ Missing required API key(s):")
    for p in problems:
        print(f"    - {p}")
    print("  Set them in .env (copy .env.example), then restart. Embeddings need a")
    print("  live call and cannot be precomputed — failing fast instead of booting broken.")
    sys.exit(1)
print("  ✓ API keys present")
PYEOF

# Few-shot examples (state_db) + schema embeddings (introspected from the target).
# Both idempotent (--skip-if-exists): embed on first boot, fast no-op on restart.
echo "◈ Seeding few-shot examples + embedding the target schema..."
python scripts/seed_fewshot_examples.py --skip-if-exists
python -m nixus.schema.reembed --skip-if-exists

echo "◈ [5/5] Starting NIXUS SQL API on :8000 ..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
