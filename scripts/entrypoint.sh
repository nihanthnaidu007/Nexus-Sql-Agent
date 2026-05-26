#!/usr/bin/env bash
set -e

echo "◈ Waiting for database to be ready..."
python - <<'PYEOF'
import asyncio, time, sys
from dotenv import load_dotenv
load_dotenv()
from db.connection import check_db_connection

for attempt in range(30):
    if asyncio.run(check_db_connection()):
        print(f"  ✓ Database ready (attempt {attempt + 1})")
        sys.exit(0)
    print(f"  attempt {attempt + 1}/30 — retrying in 2s...")
    time.sleep(2)

print("✗ Database did not become ready after 60 seconds.")
sys.exit(1)
PYEOF

echo "◈ Initializing database schema + vector tables..."
python scripts/init_db.py

echo "◈ Seeding schema embeddings (skip if exists)..."
python scripts/seed_schema_embeddings.py --skip-if-exists

echo "◈ Seeding few-shot examples (skip if exists)..."
python scripts/seed_fewshot_examples.py --skip-if-exists

echo "◈ Loading Chinook sample data (skip if already present)..."
python scripts/migrate_chinook.py --skip-if-exists

echo "◈ Starting NEXUS SQL API on :8000 ..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
