#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ -f .env ]; then
    set -a && source .env && set +a
fi

echo "◈ Initializing database..."
python scripts/init_db.py

echo "◈ Seeding schema embeddings (skip if exists)..."
python scripts/seed_schema_embeddings.py --skip-if-exists

echo "◈ Seeding few-shot examples (skip if exists)..."
python scripts/seed_fewshot_examples.py --skip-if-exists

echo "◈ Starting FastAPI (port 8000)..."
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
trap "echo '◈ Shutting down...'; kill $API_PID 2>/dev/null" EXIT INT TERM

echo "◈ Waiting for API to be ready..."
sleep 4

echo "◈ Starting Streamlit UI (port 8501)..."
streamlit run ui/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --browser.gatherUsageStats false

wait $API_PID
