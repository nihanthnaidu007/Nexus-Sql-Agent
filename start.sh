#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ -f .env ]; then
    set -a && source .env && set +a
fi

echo "◈ Initializing database..."
python scripts/init_db.py

echo "◈ Embedding target schema via introspection (skip if exists)..."
python -m nixus.schema.reembed --skip-if-exists

echo "◈ Seeding few-shot examples (skip if exists)..."
python scripts/seed_fewshot_examples.py --skip-if-exists

echo "◈ Starting FastAPI (port 8000)..."
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
trap "echo '◈ Shutting down...'; kill $API_PID 2>/dev/null" EXIT INT TERM

echo "◈ Waiting for API to be ready..."
sleep 4

echo "◈ API ready on http://localhost:8000"
echo "◈ For the React UI, run it alongside the API:"
echo "    docker compose up -d --build web   # → http://localhost:3000"
echo "    # or, for local dev:  cd web && npm install && npm run dev"

wait $API_PID
